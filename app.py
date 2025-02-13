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
import threading
import time
from threading import Event
import logging

logging.basicConfig(level=logging.INFO,
format='%(asctime)s - %(levelname)s - %(message)s')

genai.configure(api_key="AIzaSyDFSiXE-eyZBABcKZ3Tj0Ssdsm1iIRlaoE") # Replace with your actual API key or environment variable
model = genai.GenerativeModel('gemini-pro')

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(16))
ADMIN_SIGNUP_KEY = os.getenv('ADMIN_SIGNUP_KEY')

DATA_FILE = 'data.json'
task_detail_events = {}

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"users": []}
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logging.error(f"Error loading data from {DATA_FILE}: {e}", exc_info=True)
        return {"users": []}

def save_data(data):
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except IOError as e:
        logging.error(f"Error saving data to {DATA_FILE}: {e}", exc_info=True)

def get_user_data(user_id):
    data = load_data()
    user = next((u for u in data['users'] if u['id'] == user_id), None)
    return user

def update_user_data(user_id, update_func):
    data = load_data()
    user_index = next((i for i, u in enumerate(data['users']) if u['id'] == user_id), None)

    if user_index is not None:
        update_func(data['users'][user_index])
        save_data(data)
        return True
    return False


def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def admin_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or not session.get('is_admin'):
            return redirect(url_for('login')) # or perhaps a dedicated admin login page
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


def generate_context(task):
    prompt = f"""User's Name: {session.get('user_name')}
Task: "{task}"

Generate a concise and actionable context (maximum 2 sentences) that explains:
1. Why this task is important for achieving goals.
2. A quick tip or best practice for completing this task effectively.

Return only the context text without any prefixes, labels, or markdown formatting.
"""

    try:
        context_response = model.generate_content(prompt)
        context = context_response.text.strip()
        context = context.replace('**Context:**', '').replace('Context:', '').strip()
        return context
    except Exception as e:
        logging.error(f"Error generating context for task '{task}': {e}", exc_info=True)
        return "Context not available"


def generate_importance(task):
    prompt = f"""User's Name: {session.get('user_name')}
Task: "{task}"

Return EXACTLY in this format:
IMPORTANCE: [number 1-100]
"""

    try:
        response = model.generate_content(prompt)
        response_text = response.text
        importance_match = re.search(r"IMPORTANCE:\s*(\d+)", response_text)
        return importance_match.group(1) if importance_match else "50"
    except Exception as e:
        logging.error(f"Error generating importance for task '{task}': {e}", exc_info=True)
        return "50"


def generate_task_tags(task_text):
    prompt = f"""User's Name: {session.get('user_name')}
Given this task: "{task_text}"
Generate 2-3 relevant tags/categories (e.g., #work, #personal, #urgent)
Return only the tags, comma-separated."""

    try:
        response = model.generate_content(prompt)
        tags = [tag.strip() for tag in response.text.split(',')]
        return tags
    except Exception as e:
        logging.error(f"Error generating tags for task '{task_text}': {e}", exc_info=True)
        return []


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'success': False, 'message': 'Email and password are required', 'message_detail': 'Please enter your email and password.'}), 400

    all_data = load_data()
    user = next((u for u in all_data['users'] if u['email'] == email), None)

    if user and check_password_hash(user['password'], password):
        session['user_id'] = user['id']
        session['user_name'] = user['name']
        session['is_admin'] = user.get('is_admin', False) # set is_admin in session
        logging.info(f"User '{email}' logged in successfully. Admin status: {session['is_admin']}.")
        return jsonify({'success': True})

    logging.warning(f"Login attempt failed for user '{email}'. Invalid credentials.")
    return jsonify({'success': False, 'message': 'Invalid email or password', 'message_detail': 'Incorrect email or password. Please try again.'}), 401


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET':
        return render_template('signup.html')

    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    admin_key = data.get('adminKey') # optional admin key during signup

    if not name or not email or not password:
        return jsonify({'success': False, 'message': 'All fields are required', 'message_detail': 'Please fill in all the required fields for signup.'}), 400

    all_data = load_data()

    if any(u['email'] == email for u in all_data['users']):
        logging.warning(f"Signup attempt failed. Email '{email}' already exists.")
        return jsonify({'success': False, 'message': 'Email already exists', 'message_detail': 'This email address is already registered. Please use a different email or login.'}), 400

    user_id = str(uuid.uuid4())
    is_admin = False
    if ADMIN_SIGNUP_KEY and admin_key == ADMIN_SIGNUP_KEY: # check admin key against env variable
        is_admin = True

    new_user = {
        'id': user_id,
        'name': name,
        'email': email,
        'password': generate_password_hash(password),
        'goals': [],
        'settings': {},
        'is_admin': is_admin # set is_admin in user data
    }

    all_data['users'].append(new_user)
    save_data(all_data)
    logging.info(f"New user '{email}' signed up successfully. Admin: {is_admin}")

    return jsonify({'success': True})


@app.route('/logout')
def logout():
    user_id = session.get('user_id')
    user_name = session.get('user_name')
    session.clear()
    logging.info(f"User '{user_name}' (ID: {user_id}) logged out.")
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
        message = data.get('message', '').strip()
        user_name = session.get('user_name', 'User')

        if not message:
            return jsonify({"error": "Message is required"}), 400

        # Check if it's likely a task generation request
        task_keywords = ['create', 'make', 'generate', 'help me', 'todo', 'task', 'plan']
        is_task_request = any(keyword in message.lower() for keyword in task_keywords)

        if is_task_request:
            # Generate tasks
            task_prompt = f"""User's Name: {user_name}

Generate a list of specific, actionable tasks for: {message}
Return only the tasks, one per line, starting each line with "- "."""

            try:
                response = model.generate_content(task_prompt)
                if not response or not response.text:
                    raise Exception("No response from model")

                # Parse tasks
                tasks = []
                for line in response.text.strip().split('\n'):
                    if line.startswith('- '):
                        task_text = line[2:].strip()
                        if task_text:
                            tasks.append({
                                "id": str(uuid.uuid4()),
                                "text": task_text,
                                "completed": False,
                                "isGenerating": True,  # Mark as generating initially
                                "context": None,  # Will be filled by background task
                                "importance": None,  # Will be filled by background task
                                "due_date": datetime.now().strftime('%Y-%m-%d')
                            })

                if not tasks:
                    return jsonify({"error": "No tasks could be generated"}), 400

                # Create new goal with tasks
                new_goal = {
                    "id": str(uuid.uuid4()),
                    "text": message,
                    "tasks": tasks,
                    "isGenerated": True
                }

                # Add the goal to user data
                def add_new_goal(user_data):
                    user_data.setdefault('goals', []).append(new_goal)
                update_user_data(session['user_id'], add_new_goal)

                # Start background task to generate details
                task_detail_events[new_goal['id']] = Event()
                thread = threading.Thread(
                    target=generate_task_details_bg,
                    args=(session['user_id'], new_goal['id'])
                )
                thread.daemon = True
                thread.start()

                return jsonify({
                    "response": "I've created your tasks! I'm now adding more details to each task...",
                    "tasks": tasks,
                    "isGenerating": True,
                    "goalId": new_goal['id']
                })

            except Exception as e:
                logging.error(f"Task generation error: {e}", exc_info=True)
                return jsonify({"error": str(e)}), 500

        # Handle non-task messages
        try:
            chat_prompt = f"""User's Name: {user_name}
Brief helpful response for: {message}"""
            response = model.generate_content(chat_prompt)

            if not response or not response.text:
                raise Exception("No response from model")

            return jsonify({
                "response": response.text,
                "tasks": [],
                "isGenerating": False
            })

        except Exception as e:
            logging.error(f"Chat response error: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    except Exception as e:
        logging.error(f"General chat error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

def generate_task_details_bg(user_id, goal_id):
    with app.app_context():
        try:
            # Get user data first
            user_data = get_user_data(user_id)
            user_name = None
            for user in load_data().get('users', []):
                if user['id'] == user_id:
                    user_name = user.get('name', 'User')
                    break

            def update_tasks(user_data):
                for goal in user_data.get('goals', []):
                    if goal['id'] == goal_id:
                        for task in goal.get('tasks', []):
                            try:
                                # Generate context and importance for each task
                                detail_prompt = f"""User's Name: {user_name}

For the task: {task['text']}
Provide exactly in this format:
CONTEXT: (write a brief explanation why this task matters)
IMPORTANCE: (just a number 1-100)"""

                                detail_response = model.generate_content(detail_prompt)

                                if detail_response and detail_response.text:
                                    # Extract context and importance using more robust regex
                                    context_match = re.search(r"CONTEXT:\s*(.+?)(?=\n*IMPORTANCE:|$)", detail_response.text, re.DOTALL)
                                    importance_match = re.search(r"IMPORTANCE:\s*(\d+)", detail_response.text)

                                    if context_match:
                                        task['context'] = context_match.group(1).strip()
                                    else:
                                        task['context'] = "Task context not available"

                                    if importance_match:
                                        task['importance'] = importance_match.group(1)
                                    else:
                                        task['importance'] = "50"  # Default importance
                                else:
                                    task['context'] = "Task context not available"
                                    task['importance'] = "50"

                                task['isGenerating'] = False
                                logging.info(f"Generated details for task: {task['text']}")
                                time.sleep(0.5)  # Small delay between tasks

                            except Exception as task_error:
                                logging.error(f"Error generating details for task '{task['text']}': {task_error}", exc_info=True)
                                task['isGenerating'] = False
                                task['error'] = True
                                task['context'] = "Failed to generate context"
                                task['importance'] = "50"
                                continue
                        break

            # Update the tasks with generated details
            update_user_data(user_id, update_tasks)

            # Signal completion
            if goal_id in task_detail_events:
                task_detail_events[goal_id].set()

        except Exception as e:
            logging.error(f"Background task error: {e}", exc_info=True)
            # Update all tasks to error state
            def mark_tasks_error(user_data):
                for goal in user_data.get('goals', []):
                    if goal['id'] == goal_id:
                        for task in goal.get('tasks', []):
                            task['isGenerating'] = False
                            task['error'] = True
                            task['context'] = "Failed to generate context"
                            task['importance'] = "50"
            update_user_data(user_id, mark_tasks_error)

            if goal_id in task_detail_events:
                task_detail_events[goal_id].set()

@app.route('/task-details-status/<goal_id>', methods=['GET'])
@login_required
def check_task_details_status(goal_id):
    user = get_user_data(session['user_id'])
    is_complete = True

    for goal in user.get('goals', []):
        if goal['id'] == goal_id:
            for task in goal.get('tasks', []):
                if task.get('isGenerating'):
                    is_complete = False
                    break
            break

    return jsonify({
        'isComplete': is_complete,
        'goalId': goal_id
    })

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

        def update_task_status(user_data):
            for goal in user_data.get('goals', []):
                for task in goal.get('tasks', []):
                    if task['id'] == task_id:
                        task['completed'] = completed
                        if completed:
                            task['completedAt'] = datetime.now().isoformat()
                        break
        if not update_user_data(session['user_id'], update_task_status):
            return jsonify({'success': False, 'message': 'Task not found'}), 404
        return jsonify({"success": True})
    except Exception as e:
        logging.error(f"Error updating task status for task ID '{task_id}': {e}", exc_info=True)
        return jsonify({"error": str(e), "message_detail": "Failed to update task status. Please try again."}), 500


@app.route('/goal', methods=['POST'])
@login_required
def add_goal():
    try:
        data = request.get_json()
        goal_text = data.get('goal')

        if not goal_text:
            return jsonify({'success': False, 'message': 'Goal text is required', 'message_detail': 'Please provide text for your new goal.'}), 400

        def add_new_goal(user_data):
            user_data.setdefault('goals', []).append({
                'id': str(uuid.uuid4()),
                'text': goal_text,
                'tasks': [],
                'isGenerated': False
            })
        update_user_data(session['user_id'], add_new_goal)
        return jsonify({"success": True})
    except Exception as e:
        logging.error(f"Error adding new goal: {e}", exc_info=True)
        return jsonify({"error": str(e), "message_detail": "Failed to add new goal. Please try again."}), 500


@app.route('/task', methods=['POST'])
@login_required
def add_task():
    try:
        data = request.get_json()
        task_data = data.get('task')

        if not task_data or not task_data.get('text'):
            return jsonify({"error": "Task text is required", "message_detail": "Please provide text for your new task."}), 400

        new_task = {
            'id': str(uuid.uuid4()),
            'text': task_data['text'],
            'completed': False,
            'due_date': task_data.get('dueDate'),
            'context': task_data.get('context', ''),
            'importance': task_data.get('importance', '50'),
            'tags': generate_task_tags(task_data['text']),
            'isManual': True
        }

        def add_new_task(user_data):
            if not user_data.get('goals'):
                user_data['goals'] = [{
                    'id': str(uuid.uuid4()),
                    'text': 'Tasks',
                    'tasks': [],
                    'isGenerated': False
                }]
            user_data['goals'][-1]['tasks'].append(new_task)
        update_user_data(session['user_id'], add_new_task)
        return jsonify({"success": True, "task": new_task})
    except Exception as e:
        logging.error(f"Error adding new task: {e}", exc_info=True)
        return jsonify({"error": str(e), "message_detail": "Failed to add new task. Please try again."}), 500


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    user = get_user_data(session['user_id'])

    if request.method == 'GET':
        return jsonify(user.get('settings', {}))

    settings_data = request.get_json()

    def update_settings(user_data):
        user_data['settings'] = settings_data
    if update_user_data(session['user_id'], update_settings):
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Failed to save settings', 'message_detail': 'Could not save your settings. Please try again.'}), 400


@app.route('/generate-ai-settings', methods=['POST'])
@login_required
def generate_ai_settings():
    try:
        data = request.get_json()
        work_description = data.get('workDescription', '')
        user_name = session.get('user_name')
        if not work_description:
            return jsonify({"error": "Work description is required", "message_detail": "Please provide a description of your work to generate settings."}), 400

        prompt = f"""User's Name: {user_name}

Based on this work description: "{work_description}"

Generate appropriate settings in exactly this format:
    SHORT TERM FOCUS: [3-month goals and immediate priorities based on the work description]
    LONG TERM GOALS: [1-year vision and major milestones to achieve]
    SORTING PREFERENCES: [how tasks should be prioritized based on the work context]
    """

        response = model.generate_content(prompt)
        response_text = response.text

        short_term = re.search(r"SHORT TERM FOCUS:\s*(.+?)(?=LONG TERM GOALS:|$)", response_text, re.DOTALL)
        long_term = re.search(r"LONG TERM GOALS:\s*(.+?)(?=SORTING PREFERENCES:|$)", response_text, re.DOTALL)
        sorting = re.search(r"SORTING PREFERENCES:\s*(.+?)(?=|$)", response_text, re.DOTALL)

        return jsonify({
            "shortTermFocus": short_term.group(1).strip() if short_term else "",
            "longTermGoals": long_term.group(1).strip() if long_term else "",
            "sortingPreferences": sorting.group(1).strip() if sorting else ""
        })

    except Exception as e:
        logging.error(f"Error generating AI settings: {e}", exc_info=True)
        return jsonify({"error": str(e), "message_detail": "Failed to generate AI settings. Please try again later."}), 500


@app.route('/generate-tasks', methods=['POST'])
@login_required
def generate_tasks():
    try:
        data = request.get_json()
        goal_text = data.get('goalText')
        goal_id = data.get('goalId')
        user_name = session.get('user_name')

        if not goal_text or not goal_id:
            return jsonify({"error": "Goal text and ID are required", "message_detail": "Please provide both goal text and goal ID."}), 400

        user_settings = get_user_data(session['user_id']).get('settings', {})
        work_description = user_settings.get('workDescription', '')

        task_prompt_context = ""
        if work_description:
            task_prompt_context = f" considering my work description: '{work_description}', "

        task_prompt = f"""User's Name: {user_name}

Create 6 clear, actionable steps for: {goal_text}{task_prompt_context}
Even if the goal is not directly related to my work description, generate relevant and helpful tasks.
Return only the tasks, one per line. Be specific and concise."""

        task_response = model.generate_content(task_prompt)
        if not task_response or not task_response.text:
            logging.error(f"Gemini failed to generate tasks for goal '{goal_text}'.")
            return jsonify({"error": "Failed to generate tasks", "message_detail": "The AI model could not generate tasks for this goal. Please try again later."}), 500

        tasks = [t.strip() for t in task_response.text.split('\n') if t.strip()]
        new_tasks = []
        for task in tasks:
            new_tasks.append({
                'id': str(uuid.uuid4()),
                'text': task,
                'completed': False,
                'due_date': extract_date_from_text(goal_text),
                'context': '',
                'importance': '50',
                'tags': generate_task_tags(task)
            })

        def update_goal_tasks(user_data):
            for goal in user_data.get('goals', []):
                if goal['id'] == goal_id:
                    goal['tasks'] = new_tasks
                    break
        update_user_data(session['user_id'], update_goal_tasks)

        return jsonify({
            "success": True,
            "tasks": new_tasks
        })

    except Exception as e:
        logging.error(f"Error generating tasks for goal '{goal_text}': {e}", exc_info=True)
        return jsonify({"error": str(e), "message_detail": "Failed to generate tasks for this goal. Please try again later."}), 500


@app.route('/generate-task-details', methods=['POST'])
@login_required
def generate_task_details():
    try:
        data = request.get_json()
        task_id = data.get('task_id')
        task_text = data.get('task_text')
        user_name = session.get('user_name')

        if not task_text or not task_id:
            return jsonify({"error": "Task text and ID required", "message_detail": "Please provide both task text and task ID."}), 400

        prompt = f"""User's Name: {user_name}

For the task: "{task_text}"
Return EXACTLY in this format:
CONTEXT: [one quick tip in 3-5 words only] just the context without numbers  or any other information
IMPORTANCE: [number 1-100]
"""

        response = model.generate_content(prompt)
        response_text = response.text

        context_match = re.search(r"CONTEXT:\s*(.*?)(?=IMPORTANCE:|$)", response_text, re.DOTALL)
        importance_match = re.search(r"IMPORTANCE:\s*(\d+)", response_text)

        context = context_match.group(1).strip() if context_match else ""
        importance = importance_match.group(1) if importance_match else "50"

        def update_task_details(user_data):
            for goal in user_data.get('goals', []):
                for task in goal.get('tasks', []):
                    if task['id'] == task_id:
                        task['context'] = context
                        task['importance'] = importance
        update_user_data(session['user_id'], update_task_details)

        return jsonify({
            "success": True,
            "context": context,
            "importance": importance
        })

    except Exception as e:
        logging.error(f"Error generating task details for task '{task_text}': {e}", exc_info=True)
        return jsonify({"error": str(e), "message_detail": "Failed to generate task details. Please try again later."}), 500


@app.route('/task/<task_id>', methods=['DELETE'])
@login_required
def delete_task(task_id):
    try:
        def remove_task(user_data):
            for goal in user_data.get('goals', []):
                goal['tasks'] = [t for t in goal.get('tasks', []) if t['id'] != task_id]
        if not update_user_data(session['user_id'], remove_task):
            return jsonify({'success': False, 'message': 'Task not found'}), 404
        return jsonify({"success": True})
    except Exception as e:
        logging.error(f"Error deleting task with ID '{task_id}': {e}", exc_info=True)
        return jsonify({"error": str(e), "message_detail": "Failed to delete task. Please try again."}), 500

@app.route('/update-task', methods=['POST'])
@login_required
def update_task_details():
    try:
        data = request.get_json()
        task_id = data.get('taskId')
        task_text = data.get('text')
        due_date = data.get('dueDate')
        context = data.get('context')
        importance = data.get('importance')

        if not task_id:
            return jsonify({"error": "Task ID is required", "message_detail": "Please provide the ID of the task to update."}), 400

        task_found = False
        def update_task_info(user_data):
            nonlocal task_found
            for goal in user_data.get('goals', []):
                for task in goal.get('tasks', []):
                    if task['id'] == task_id:
                        task_found = True
                        task['text'] = task_text
                        task['due_date'] = due_date
                        task['context'] = context
                        task['importance'] = importance
                        break
                if task_found:
                    break

        if not update_user_data(session['user_id'], update_task_info):
            return jsonify({'success': False, 'message': 'User not found'}), 404

        if not task_found:
            return jsonify({"error": "Task not found", "message_detail": "The task with the provided ID could not be found."}), 404

        return jsonify({"success": True})
    except Exception as e:
        logging.error(f"Error updating task details for task ID '{task_id}': {e}", exc_info=True)
        return jsonify({"error": str(e), "message_detail": "Failed to update task details. Please try again."}), 500


def get_task_category(due_date):
    if not due_date:
        return "today"  # Default to today if no date

    try:
        due_date = datetime.strptime(due_date, '%Y-%m-%d').date()
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)

        if due_date < today:
            return "today"  # Past due tasks show in today
        elif due_date == today:
            return "today"
        elif due_date == tomorrow:
            return "tomorrow"
        else:
            return "future"
    except (ValueError, TypeError):
        return "today"  # Handle invalid date formats gracefully


@app.route('/tasks/categorized', methods=['GET'])
@login_required
def get_categorized_tasks():
    user = get_user_data(session['user_id'])

    categorized_tasks = {
        "today": [],
        "tomorrow": [],
        "future": []
    }

    goals = user.get('goals', [])
    if goals:
        latest_goal = goals[-1]

        ai_tasks = []
        manual_tasks = []

        for task in latest_goal.get('tasks', []):
            task_with_goal = {
                **task,
                'goalId': latest_goal['id'],
                'goalText': latest_goal['text']
            }
            if task.get('isManual', False):
                manual_tasks.append(task_with_goal)
            else:
                ai_tasks.append(task_with_goal)

        for task in ai_tasks:
            category = get_task_category(task.get('due_date'))
            categorized_tasks[category].append(task)

        for task in manual_tasks:
            category = get_task_category(task.get('due_date'))
            categorized_tasks[category].append(task)

    return jsonify(categorized_tasks)


@app.route('/task/move', methods=['POST'])
@login_required
def move_task():
    try:
        data = request.get_json()
        task_id = data.get('taskId')
        new_date = data.get('newDate')

        def update_task_date(user_data):
            for goal in user_data.get('goals', []):
                for task in goal.get('tasks', []):
                    if task['id'] == task_id:
                        task['due_date'] = new_date
                        break
        if not update_user_data(session['user_id'], update_task_date):
            return jsonify({'success': False, 'message': 'Task not found'}), 404
        return jsonify({"success": True})
    except Exception as e:
        logging.error(f"Error moving task with ID '{task_id}' to new date: {e}", exc_info=True)
        return jsonify({"error": str(e), "message_detail": "Failed to move task. Please try again."}), 500


@app.route('/task-stats', methods=['GET'])
@login_required
def get_task_stats():
    user = get_user_data(session['user_id'])
    stats = {
        'total_tasks': 0,
        'completed_tasks': 0,
        'completion_rate': 0,
        'tasks_by_priority': {'high': 0, 'medium': 0, 'low': 0},
        'tasks_by_category': {'today': 0, 'tomorrow': 0, 'future': 0}
    }

    if user.get('goals'):
        latest_goal = user['goals'][-1]
        tasks = latest_goal.get('tasks', [])

        stats['total_tasks'] = len(tasks)
        stats['completed_tasks'] = sum(1 for t in tasks if t.get('completed'))
        stats['completion_rate'] = (stats['completed_tasks'] / stats['total_tasks'] * 100) if stats['total_tasks'] > 0 else 0

        for task in tasks:
            importance = int(task.get('importance', 0))
            if importance > 75:
                stats['tasks_by_priority']['high'] += 1
            elif importance > 50:
                stats['tasks_by_priority']['medium'] += 1
            else:
                stats['tasks_by_priority']['low'] += 1

            category = get_task_category(task.get('due_date'))
            stats['tasks_by_category'][category] += 1

    return jsonify(stats)


@app.route('/users/all', methods=['GET'])
@login_required
@admin_required
def get_all_users_admin():
    data = load_data()
    search_term = request.args.get('search', '').lower()
    users_data = []
    for user in data['users']:
        if search_term in user['name'].lower() or search_term in user['email'].lower():
            users_data.append({"id": user['id'], "name": user['name'], "email": user['email'], "settings": user.get('settings', {})}) #Include settings here for search if needed
    return jsonify(users_data)

@app.route('/tasks/all', methods=['GET'])
@login_required
@admin_required
def get_all_tasks_admin():
    data = load_data()
    all_tasks = []
    search_term = request.args.get('search', '').lower()

    for user in data['users']:
        for goal in user.get('goals', []):
            for task in goal.get('tasks', []):
                task_text_lower = task['text'].lower()
                goal_name_lower = goal['text'].lower()
                if search_term in task_text_lower or search_term in goal_name_lower:
                    task_with_goal_user = {
                        **task,
                        'goalId': goal['id'],
                        'goalName': goal['text'],
                        'userId': user['id'],
                        'userName': user['name'],
                        'userEmail': user['email']
                    }
                    all_tasks.append(task_with_goal_user)
    return jsonify(all_tasks)

@app.route('/user/<user_id>/details', methods=['GET'])
@login_required
@admin_required
def get_user_details_admin(user_id):
    data = load_data()
    user_data = next((u for u in data['users'] if u['id'] == user_id), None)
    if not user_data:
        return jsonify({'message': 'User not found'}), 404

    user_tasks = []
    user_goals = user_data.get('goals', [])
    user_settings = user_data.get('settings', {}) # Get user settings

    for goal in user_goals:
        for task in goal.get('tasks', []):
            task_with_goal = {
                **task,
                'goalId': goal['id'],
                'goalName': goal['text']
            }
            user_tasks.append(task_with_goal)

    user_details = {
        'user': {"id": user_data['id'], "name": user_data['name'], "email": user_data['email'], "settings": user_settings}, # Include settings here
        'tasks': user_tasks,
        'goals': user_goals
    }
    return jsonify(user_details)

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    return render_template('admin_dashboard.html')

def check_due_tasks():
    now = datetime.now()
    tomorrow = now + timedelta(days=1)

    users = load_data().get('users', [])
    notifications = []

    for user in users:
        if user.get('goals'):
            latest_goal = user['goals'][-1]
            for task in latest_goal.get('tasks', []):
                if not task.get('completed') and task.get('due_date'):
                    try:
                        due_date = datetime.strptime(task.get('due_date'), '%Y-%m-%d')
                        if due_date.date() == now.date():
                            notifications.append({
                                'user_id': user['id'],
                                'task_id': task['id'],
                                'message': f"Task due today: {task['text']}"
                            })
                        elif due_date.date() == tomorrow.date():
                            notifications.append({
                                'user_id': user['id'],
                                'task_id': task['id'],
                                'message': f"Task due tomorrow: {task['text']}"
                            })
                    except ValueError:
                        logging.warning(f"Invalid date format for task '{task['text']}', task ID: {task['id']}")
                        continue

    return notifications


def generate_task_dependencies(tasks):
    dependencies = []
    for i, task in enumerate(tasks):
        if i > 0:
            prompt = f"""User's Name: {session.get('user_name')}
Given these two tasks:
1. {tasks[i-1]['text']}
2. {task['text']}

Should task 2 depend on task 1? Answer only YES or NO."""

            try:
                response = model.generate_content(prompt)
                if 'YES' in response.text.upper():
                    dependencies.append({
                        'dependent': task['id'],
                        'dependency': tasks[i-1]['id']
                    })
            except Exception as e:
                logging.error(f"Error generating dependency for tasks '{tasks[i-1]['text']}' and '{task['text']}': {e}", exc_info=True)
                continue

    return dependencies


def generate_task_suggestions(user_id):
    user = get_user_data(user_id)
    settings = user.get('settings', {})
    completed_tasks = []
    user_name = user.get('name')

    if user.get('goals'):
        latest_goal = user['goals'][-1]
        completed_tasks = [t['text'] for t in latest_goal.get('tasks', []) if t.get('completed')]

    prompt = f"""User's Name: {user_name}

Based on:
- Work description: {settings.get('workDescription')}
- Completed tasks: {', '.join(completed_tasks)}

Suggest 3 new tasks that would be logical next steps.
Return only the tasks, one per line."""

    try:
        response = model.generate_content(prompt)
        return [task.strip() for task in response.text.split('\n') if task.strip()]
    except Exception as e:
        logging.error(f"Error generating task suggestions for user ID '{user_id}': {e}", exc_info=True)
        return []


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)