from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import google.generativeai as genai
import json
import os
import uuid
from dotenv import load_dotenv
from datetime import datetime, timedelta
import re
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import random

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(16))
genai.configure(api_key="AIzaSyCCweyAlsV6FJ3pEhe8mLhoRKnFEe55A6w")  # <-- **REPLACE WITH YOUR ACTUAL API KEY HERE**
model = genai.GenerativeModel('gemini-2.0-pro-exp-02-05')

DATA_FILE = 'data.json'

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Thread pool for generating context and importance asynchronously
executor = ThreadPoolExecutor(max_workers=8)

# Load data once at startup
app_data = None


def load_data():
    global app_data
    if app_data is None:
        try:
            if not os.path.exists(DATA_FILE):
                app_data = {"users": []}
                return app_data
            with open(DATA_FILE, 'r') as f:
                app_data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading data: {e}")
            app_data = {"users": []}
    return app_data


def save_data():
    global app_data
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(app_data, f, indent=2)
    except IOError as e:
        logger.error(f"Error saving data: {e}")


@app.teardown_appcontext
def teardown_appcontext(exception=None):
    if exception:
        logger.error(f"Teardown with exception: {exception}")
    save_data()


def get_user_data(user_id):
    data = load_data()
    user = next((u for u in data['users'] if u['id'] == user_id), None)
    return user


def update_user_data(user_id, update_func):
    data = load_data()
    user_index = next((i for i, u in enumerate(data['users']) if u['id'] == user_id), None)
    if user_index is not None:
        update_func(data['users'][user_index])
        save_data()
        return True
    return False


def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    decorated_function.__name__ = f.__name__
    return decorated_function


def extract_date_from_text(text):
    patterns = [
        r'by\s+(\d{1,2}(?:st|nd|rd|th)?\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{4})',
        r'due\s+(?:on|by)?\s+(\d{1,2}(?:st|nd|rd|th)?\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{4})',
        r'deadline[:\s]+(\d{1,2}(?:st|nd|rd|th)?\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{4})',
        r'(\d{1,2}(?:st|nd|rd|th)?\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{4})',
        r'next\s+week',
        r'next\s+month',
        r'tomorrow',
        r'in\s+(\d+)\s+days?',
        r'in\s+(\d+)\s+weeks?',
        r'in\s+(\d+)\s+months?'
    ]

    text = text.lower()
    today = datetime.now()

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            if 'next week' in match.group():
                return (today + timedelta(days=7)).strftime('%Y-%m-%d')
            elif 'next month' in match.group():
                next_month = today.replace(day=1) + timedelta(days=32)
                return next_month.replace(day=1).strftime('%Y-%m-%d')
            elif 'tomorrow' in match.group():
                return (today + timedelta(days=1)).strftime('%Y-%m-%d')
            elif 'in' in match.group():
                number = int(match.group(1))
                if 'day' in match.group():
                    return (today + timedelta(days=number)).strftime('%Y-%m-%d')
                elif 'week' in match.group():
                    return (today + timedelta(weeks=number)).strftime('%Y-%m-%d')
                elif 'month' in match.group():
                    next_month = today.replace(day=1)
                    for _ in range(number):
                        next_month = next_month + timedelta(days=32)
                        next_month = next_month.replace(day=1)
                    return next_month.strftime('%Y-%m-%d')
            else:
                try:
                    date_str = match.group(1)
                    date_str = re.sub(r'(?<=\d)(st|nd|rd|th)', '', date_str)
                    parsed_date = datetime.strptime(date_str, '%d %B %Y')
                    return parsed_date.strftime('%Y-%m-%d')
                except ValueError:
                    pass
    return today.strftime('%Y-%m-%d')


def generate_context(task, user_settings):
    prompt = f"""
Considering the user's profile, provide a relevant context tip for the given task.
The context tip should be a single, actionable piece of advice to aid in completing the task, limited to 3-5 words.

User Profile:
Work: {user_settings.get('workDescription', '')}
Short-term Focus: {user_settings.get('shortTermFocus', '')}
Long-term Goals: {user_settings.get('longTermGoals', '')}
Preferences: {user_settings.get('sortingPreferences', '')}

Task: "{task}"

Respond EXACTLY in this format:
CONTEXT: [Concise tip for the task]

Example:
CONTEXT: Break into subtasks
"""
    try:
        response = model.generate_content(prompt)
        response_text = response.text
        context_match = re.search(r"CONTEXT:\s*(.*?)(?=|$)", response_text, re.DOTALL)
        return context_match.group(1).strip() if context_match else ""
    except Exception as e:
        logger.error(f"Error generating context for task '{task}': {e}")
        return ""


def generate_importance(task, user_settings):
    prompt = f"""
Considering the user's profile, assess the importance of the given task on a scale of 1 to 100, where 1 represents the least important and 100 the most.

User Profile:
Work: {user_settings.get('workDescription', '')}
Short-term Focus: {user_settings.get('shortTermFocus', '')}
Long-term Goals: {user_settings.get('longTermGoals', '')}
Preferences: {user_settings.get('sortingPreferences', '')}

Task: "{task}"

Respond EXACTLY in this format:
IMPORTANCE: [Importance score from 1-100]

Example:
IMPORTANCE: 80
"""
    try:
        response = model.generate_content(prompt)
        response_text = response.text
        importance_match = re.search(r"IMPORTANCE:\s*(\d+)", response_text)
        return importance_match.group(1) if importance_match else "50"
    except Exception as e:
        logger.error(f"Error generating importance for task '{task}': {e}")
        return "50"


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        all_data = load_data()
        user = next((u for u in all_data['users'] if u['email'] == email), None)
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': 'Invalid email or password'}), 401
    except Exception as e:
        logger.exception("Error during login:")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET':
        return render_template('signup.html')
    try:
        data = request.get_json()
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')
        all_data = load_data()
        if any(u['email'] == email for u in all_data['users']):
            return jsonify({'success': False, 'message': 'Email already exists'}), 400
        user_id = str(uuid.uuid4())
        new_user = {
            'id': user_id,
            'name': name,
            'email': email,
            'password': generate_password_hash(password),
            'goals': [],
            'settings': {}
        }
        all_data['users'].append(new_user)
        save_data()
        return jsonify({'success': True})
    except Exception as e:
        logger.exception("Error during signup:")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/')
@login_required
def index():
    user = get_user_data(session['user_id'])
    return render_template('index.html', goals=user.get('goals', []))


@app.route('/chat', methods=['POST'])
@login_required
def chat():
    try:
        data = request.get_json()
        message = data.get('message', '')

        user = get_user_data(session['user_id'])
        settings = user.get('settings', {})
        user_settings = user.get('settings', {})

        goal_keywords = ['help me with', 'steps to', 'how to', 'guide to', 'process for',
                         'can you help me', 'what are the steps', 'explain how to',
                         'walk me through', 'give me a guide', 'how do i', 'how can i',
                         'tell me how to', 'instruct me on', 'advise me on']

        is_goal_request = any(keyword in message.lower() for keyword in goal_keywords)

        prompt = f"""
    As Dia, a helpful personal assistant, respond to the user's message.
    The response should be concise, limited to 1-2 sentences.

    User Message: "{message}"

    Response:


    IMPORTANT INFORMATIONS: when the user say hi or hey answer whit this Hello!How can I assist you today? 😊


    """
        response = model.generate_content(prompt)

        new_goal = {
            "id": str(uuid.uuid4()),
            "text": message,
            "tasks": []
        }

        if is_goal_request:
            task_prompt = f"""
        Based on the user's profile and message, suggest 6 clear, actionable steps that the user could take.
        These steps should be directly related to the user's request.
        Keep the tasks short and to the point.

        User Profile:
        Work: {user_settings.get('workDescription', '')}
        Short-term Focus: {user_settings.get('shortTermFocus', '')}
        Long-term Goals: {user_settings.get('longTermGoals', '')}
        Preferences: {user_settings.get('sortingPreferences', '')}

        User Message: {message}

        Actionable Steps:
        (Each step on a new line) and don't tell them like Here are six actionable steps or somethinh just return the steps each step on a new line
        """
            task_response = model.generate_content(task_prompt)
            tasks = task_response.text.split('\n')

            task_futures = []
            for task in tasks:
                task = task.strip()
                if task:
                    task_id = str(uuid.uuid4())
                    task_futures.append({
                        'task': task,
                        'task_id': task_id,
                        'future_context': executor.submit(generate_context, task, user_settings),
                        'future_importance': executor.submit(generate_importance, task, user_settings)
                    })

            for future in as_completed([f['future_context'] for f in task_futures] + [f['future_importance'] for f in task_futures]):
                try:
                    completed_task = next((t for t in task_futures if t['future_context'] == future or t['future_importance'] == future), None)
                    if completed_task:
                        if completed_task['future_context'] == future:
                            completed_task['context'] = future.result()
                        elif completed_task['future_importance'] == future:
                            completed_task['importance'] = future.result()
                except Exception as e:
                    logger.error(f"Error processing a task future: {e}")

            for task_data in task_futures:
                try:
                    task = task_data['task']
                    task_id = task_data['task_id']
                    context = task_data.get('context', "")
                    importance = task_data.get('importance', "50")
                    logger.info(f"Task: {task}, Context: {context}, Importance: {importance}")
                    new_task = {
                        'id': task_id,
                        'text': task,
                        'completed': False,
                        'due_date': extract_date_from_text(message),
                        'context': context,
                        'importance': importance
                    }
                    new_goal['tasks'].append(new_task)
                except Exception as e:
                    logger.error(f"Error creating task object: {e}")

            success_messages = [
                "I've created a set of tasks to help you with that!",
                "Consider it done! I've broken down your request into actionable steps.",
                "Tasks generated successfully! Let me know how else I can assist.",
                "I've laid out a plan for you. Check out the new tasks!",
                "Here are some steps to get you started!",
                "I have created the tasks to make sure you get success"
            ]
            success_message = random.choice(success_messages)

        def add_new_goal(user_data):
            if 'goals' not in user_data:
                user_data['goals'] = []
            if is_goal_request:
                user_data['goals'].append(new_goal)

        update_user_data(session['user_id'], add_new_goal)

        if is_goal_request:
            return jsonify({
                "response": success_message,
                "tasks": new_goal['tasks']
            })
        else:
            return jsonify({
                "response": response.text,
                "tasks": []
            })

    except Exception as e:
        logger.exception("Error during chat:")
        return jsonify({"error": str(e)}), 500


@app.route('/goals', methods=['GET'])
@login_required
def get_goals():
    user = get_user_data(session['user_id'])
    return jsonify(user.get('goals', []))


@app.route('/task', methods=['PUT'])
@login_required
def update_task():
    try:
        data = request.get_json()
        task_id = data.get('taskId')
        completed = data.get('completed')
        goal_id = data.get('goalId')  # Get goal_id from request

        def update_task_status(user_data):
            for goal in user_data.get('goals', []):
                if goal['id'] == goal_id:  # **Use goal_id to find the correct goal**
                    for task in goal.get('tasks', []):
                        if task['id'] == task_id:
                            task['completed'] = completed
                            if completed:
                                task['completedAt'] = datetime.now().isoformat()
                            return  # Exit after updating the task
                    return  # Exit if task_id not found in this goal
            return  # Exit if goal_id not found

        update_user_data(session['user_id'], update_task_status)
        return jsonify({"success": True})
    except Exception as e:
        logger.exception("Error updating task:")
        return jsonify({"error": str(e)}), 500


@app.route('/goal', methods=['POST'])
@login_required
def add_goal():
    try:
        data = request.get_json()
        goal_text = data.get('goal')

        def add_new_goal(user_data):
            if 'goals' not in user_data:
                user_data['goals'] = []
            user_data['goals'].append({
                'id': str(uuid.uuid4()),
                'text': goal_text,
                'tasks': []
            })

        update_user_data(session['user_id'], add_new_goal)
        return jsonify({"success": True})
    except Exception as e:
        logger.exception("Error adding goal:")
        return jsonify({"error": str(e)}), 500


@app.route('/task', methods=['POST'])
@login_required
def add_task():
    try:
        data = request.get_json()
        goal_id = data.get('goalId')
        task_data = data.get('task')

        def add_new_task(user_data):
            for goal in user_data.get('goals', []):
                if goal['id'] == goal_id:
                    if 'tasks' not in goal:
                        goal['tasks'] = []
                    new_task = {
                        'id': str(uuid.uuid4()),
                        'text': task_data['text'],
                        'completed': False,  # Explicitly set completed to False here
                        'due_date': task_data.get('dueDate', ''),
                        'context': task_data.get('context', ''),
                        'importance': task_data.get('importance', '50')
                    }
                    goal['tasks'].append(new_task)
                    break

        update_user_data(session['user_id'], add_new_task)
        return jsonify({"success": True})
    except Exception as e:
        logger.exception("Error adding task:")
        return jsonify({"error": str(e)}), 500


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    user = get_user_data(session['user_id'])

    if request.method == 'GET':
        return jsonify(user.get('settings', {}))

    try:
        settings_data = request.get_json()

        def update_settings(user):
            user['settings'] = settings_data

        if update_user_data(session['user_id'], update_settings):
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': 'Failed to save settings'}), 400
    except Exception as e:
        logger.exception("Error during settings update:")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500


@app.route('/generate-ai-settings', methods=['POST'])
@login_required
def generate_ai_settings():
    try:
        data = request.get_json()
        message = data.get('message', '')
        if not message:
            return jsonify({"error": "No message provided"}), 400

        prompt = f"""
    Analyze the following statement and extract key information to define the user's work description, short-term focus, long-term goals, and preferred sorting style.

    Statement: {message}

    Provide the results in a structured format as follows:
    Work Description: [A concise description of the user's work or profession]
    Short Term Focus: [The user's immediate priorities and areas of concentration]
    Long Term Goals: [The user's aspirations and objectives for the future]
    Sorting Preferences: [How the user prefers to organize and prioritize their tasks or information]
    """
        response = model.generate_content(prompt)
        response_text = response.text

        try:
            work_match = re.search(r"Work Description:\s*(.+)", response_text)
            short_match = re.search(r"Short Term Focus:\s*(.+)", response_text)
            long_match = re.search(r"Long Term Goals:\s*(.+)", response_text)
            sort_match = re.search(r"Sorting Preferences:\s*(.+)", response_text)

            work = work_match.group(1).strip() if work_match else ""
            short = short_match.group(1).strip() if short_match else ""
            long = long_match.group(1).strip() if long_match else ""
            sort = sort_match.group(1).strip() if sort_match else ""

            return jsonify({
                "workDescription": work,
                "shortTermFocus": short,
                "longTermGoals": long,
                "sortingPreferences": sort
            })
        except Exception as e:
            logger.error(f"Error parsing settings: {e}")
            return jsonify({
                "workDescription": "",
                "shortTermFocus": "",
                "longTermGoals": "",
                "sortingPreferences": ""
            }), 500
    except Exception as e:
        logger.exception("Error generating AI settings:")
        return jsonify({"error": str(e)}), 500


@app.route('/generate-task-details', methods=['POST'])
@login_required
def generate_task_details():
    try:
        data = request.get_json()
        task_text = data.get('task_text')

        if not task_text:
            return jsonify({"error": "No task text provided"}), 400

        user = get_user_data(session['user_id'])
        settings = user.get('settings', {})
        settings_context = f"""User's Profile:
        Work: {settings.get('workDescription', '')}
        Short-term Focus: {settings.get('shortTermFocus', '')}
        Long-term Goals: {settings.get('longTermGoals', '')}
        Preferences: {settings.get('sortingPreferences', '')}
    """
        future_context = executor.submit(generate_context, task_text, settings)
        future_importance = executor.submit(generate_importance, task_text, settings)

        try:  # Nested try block
            context = future_context.result()
            importance = future_importance.result()
            return jsonify({
                "context": context,
                "importance": importance
            })
        except Exception as e:  # Inner except block
            logger.error(f"Error processing task '{task_text}': {e}")
            return jsonify({"error": str(e)}), 500
    except Exception as e:  # Outer except block
        logger.exception("Error generating task details:")
        return jsonify({"error": str(e)}), 500


@app.route('/task/<goal_id>/<task_id>', methods=['DELETE'])
@login_required
def delete_task(goal_id, task_id):
    try:
        def remove_task(user_data):
            for goal in user_data.get('goals', []):
                if goal['id'] == goal_id:
                    goal['tasks'] = [t for t in goal.get('tasks', []) if t['id'] != task_id]
                    break

        update_user_data(session['user_id'], remove_task)
        return jsonify({"success": True})
    except Exception as e:
        logger.exception("Error deleting task:")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    load_data()
    app.run(host='0.0.0.0', port=8080)
