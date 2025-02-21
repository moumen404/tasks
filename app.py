from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import google.generativeai as genai
import os
import uuid
from datetime import datetime, timedelta
import re
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import threading
import time
from threading import Event
import logging
from pymongo import MongoClient
from pymongo.errors import ConfigurationError, ConnectionFailure

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Hardcoded environment variables
MONGODB_URI = "mongodb+srv://diatask:diataskpassword@cluster0.y7ocx.mongodb.net/my_database?retryWrites=true&w=majority"
GEMINI_API_KEY = "AIzaSyCKcbHo3lbOzPL5k7hI1IsU5D8XtLkFODA"
SECRET_KEY = secrets.token_hex(16)  # Generates a secure random key
ADMIN_SIGNUP_KEY = "your_admin_signup_key_here"  # Replace with your admin key

app = Flask(__name__)
app.secret_key = SECRET_KEY

# MongoDB Connection
def get_db():
    try:
        if not MONGODB_URI:
            raise ValueError("MONGODB_URI is not set")
        client = MongoClient(MONGODB_URI)
        return client['my_database']
    except (ConfigurationError, ConnectionFailure, ValueError) as e:
        logging.error(f"Failed to connect to MongoDB: {e}")
        raise Exception(f"Database connection failed: {e}")

# Initialize Database with Admin User
def init_db():
    try:
        db = get_db()
        if db.users.count_documents({}) == 0:
            admin_password_hash = generate_password_hash('password')
            admin_user = {
                "id": str(uuid.uuid4()),
                "name": "Admin User",
                "email": "admin@example.com",
                "password": admin_password_hash,
                "goals": [],
                "settings": {},
                "is_admin": True
            }
            db.users.insert_one(admin_user)
            logging.info("Initialized database with admin user")
    except Exception as e:
        logging.error(f"Database initialization failed: {e}")
        raise

# Initialize database when the app starts
try:
    init_db()
except Exception as e:
    logging.error(f"Application startup failed due to database error: {e}")
    exit(1)

# API Key Configuration
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

task_detail_events = {}

def format_gemini_response(text):
    text = re.sub(r'\*\*|__|\*', '', text)
    text = re.sub(r'_', '', text)
    text = re.sub(r'#+\s*', '', text)
    text = re.sub(r'^[\s]*[-+*]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[\s]*\d+\.\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    text = re.sub(r'`.*?`', '', text)
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
    text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    return text

def get_user_data(user_id):
    db = get_db()
    user = db.users.find_one({"id": user_id})
    if user:
        user['_id'] = str(user['_id'])
    return user

def update_user_data(user_id, update_func):
    db = get_db()
    user = db.users.find_one({"id": user_id})
    if user:
        update_func(user)
        db.users.update_one({"id": user_id}, {"$set": user})
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

def generate_context(task):
    prompt = f"""User's Name: {session.get('user_name')}
Task: "{task}"
Generate a concise and actionable context (maximum 2 sentences) that explains:
Why this task is important for achieving goals.
A quick tip or best practice for completing this task effectively.
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
        try:
            return render_template('login.html')
        except Exception as e:
            return jsonify({"error": "GET request requires templates, which may not be available on Vercel", "details": str(e)}), 500
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        return jsonify({'success': False, 'message': 'Email and password are required'}), 400
    db = get_db()
    user = db.users.find_one({"email": email})
    if user and check_password_hash(user['password'], password):
        session['user_id'] = user['id']
        session['user_name'] = user['name']
        session['is_admin'] = user.get('is_admin', False)
        logging.info(f"User '{email}' logged in successfully")
        return jsonify({'success': True})
    logging.warning(f"Login attempt failed for user '{email}'")
    return jsonify({'success': False, 'message': 'Invalid email or password'}), 401

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET':
        try:
            return render_template('signup.html')
        except Exception as e:
            return jsonify({"error": "GET request requires templates, which may not be available on Vercel", "details": str(e)}), 500
    data = request.get_json() or {}
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    admin_key = data.get('adminKey')
    if not name or not email or not password:
        return jsonify({'success': False, 'message': 'All fields are required'}), 400
    db = get_db()
    if db.users.find_one({"email": email}):
        logging.warning(f"Signup attempt failed. Email '{email}' already exists")
        return jsonify({'success': False, 'message': 'Email already exists'}), 400
    user_id = str(uuid.uuid4())
    is_admin = False
    if ADMIN_SIGNUP_KEY and admin_key == ADMIN_SIGNUP_KEY:
        is_admin = True
    new_user = {
        'id': user_id,
        'name': name,
        'email': email,
        'password': generate_password_hash(password),
        'goals': [],
        'settings': {},
        'is_admin': is_admin
    }
    db.users.insert_one(new_user)
    logging.info(f"New user '{email}' signed up successfully. Admin: {is_admin}")
    return jsonify({'success': True})

@app.route('/logout')
def logout():
    user_id = session.get('user_id')
    user_name = session.get('user_name')
    session.clear()
    logging.info(f"User '{user_name}' (ID: {user_id}) logged out")
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    try:
        user = get_user_data(session['user_id'])
        return render_template('index.html', goals=user.get('goals', []))
    except Exception as e:
        return jsonify({"error": "Rendering templates may not work on Vercel without static setup", "details": str(e)}), 500

@app.route('/chat', methods=['POST'])
@login_required
def chat():
    try:
        data = request.get_json() or {}
        message = data.get('message', '').strip()
        user_name = session.get('user_name', 'User')
        if not message:
            return jsonify({"error": "Message is required"}), 400
        if message.lower() == '/help':
            help_message = """
How to talk to the AI:
General Chat: Just type your message! The AI will respond helpfully.
Generate Tasks: To ask the AI to create tasks, use phrases like:
"Create tasks for [your topic]"
"Help me plan [your goal]"
"Generate a to-do list for [activity]"
Using Your Settings for Task Generation:
To make the AI consider your user settings (like work description, short-term/long-term goals) when generating tasks, include the phrase "my settings" in your prompt.
Example: "Create tasks for project planning based on my settings."
The AI will then try to generate tasks that are relevant to your work and goals as defined in your settings.
To NOT use settings: Simply omit "my settings" from your prompt, and the AI will generate tasks more generally.
"""
            return jsonify({"response": format_gemini_response(help_message), "tasks": [], "isGenerating": False})

        task_keywords = ['create', 'make', 'generate', 'help me', 'todo', 'task', 'plan']
        is_task_request = any(keyword in message.lower() for keyword in task_keywords)

        if is_task_request:
            task_prompt_base = f"""User's Name: {user_name}
Generate a list of specific, actionable tasks for: {message}
Return only the tasks, one per line, starting each line with "- "."""
            use_settings = "my settings" in message.lower()
            task_prompt_context = ""
            if use_settings:
                user_settings = get_user_data(session['user_id']).get('settings', {})
                work_description = user_settings.get('workDescription', '')
                short_term_focus = user_settings.get('shortTermFocus', '')
                long_term_goals = user_settings.get('longTermGoals', '')
                user_email = user_settings.get('email', '')
                context_parts = []
                if work_description:
                    context_parts.append(f"Work Description: '{work_description}'")
                if short_term_focus:
                    context_parts.append(f"Short Term Focus: '{short_term_focus}'")
                if long_term_goals:
                    context_parts.append(f"Long Term Goals: '{long_term_goals}'")
                if context_parts:
                    settings_context = "Considering my user settings: " + ", ".join(context_parts) + ". "
                    task_prompt = f"""User's Name: {user_name} - User Email: {user_email}
{settings_context}
Create a list of specific, actionable tasks for: {message}
Make sure the tasks are relevant to my settings and help me achieve my goals.
Return only the tasks, one per line, starting each line with "- "."""
                else:
                    task_prompt = f"""User's Name: {user_name}
Create a list of specific, actionable tasks for: {message}
You were asked to consider user settings, but no relevant settings are available. Generate general tasks for: {message}
Return only the tasks, one per line, starting each line with "- "."""
            else:
                task_prompt = task_prompt_base

            try:
                response = model.generate_content(task_prompt)
                if not response or not response.text:
                    raise Exception("No response from model")
                tasks = []
                for line in response.text.strip().split('\n'):
                    if line.startswith('- '):
                        task_text = line[2:].strip()
                        if task_text:
                            tasks.append({
                                "id": str(uuid.uuid4()),
                                "text": task_text,
                                "completed": False,
                                "isGenerating": True,
                                "context": None,
                                "importance": None,
                                "due_date": datetime.now().strftime('%Y-%m-%d')
                            })
                if not tasks:
                    return jsonify({"error": "No tasks could be generated"}), 400
                new_goal = {
                    "id": str(uuid.uuid4()),
                    "text": message,
                    "tasks": tasks,
                    "isGenerated": True
                }
                def add_new_goal(user_data):
                    user_data.setdefault('goals', []).append(new_goal)
                update_user_data(session['user_id'], add_new_goal)
                task_detail_events[new_goal['id']] = Event()
                thread = threading.Thread(
                    target=generate_task_details_bg,
                    args=(session['user_id'], new_goal['id'])
                )
                thread.daemon = True
                thread.start()
                response_message = "I've created your tasks!"
                if use_settings:
                    response_message = "Considering your settings, I've created your tasks!"
                response_message += " I'm now adding more details to each task..."
                return jsonify({
                    "response": format_gemini_response(response_message),
                    "tasks": tasks,
                    "isGenerating": True,
                    "goalId": new_goal['id']
                })
            except Exception as e:
                logging.error(f"Task generation error: {e}", exc_info=True)
                return jsonify({"error": str(e)}), 500

        try:
            chat_prompt = f"""User's Name: {user_name}
Brief helpful response for: {message}"""
            response = model.generate_content(chat_prompt)
            if not response or not response.text:
                raise Exception("No response from model")
            return jsonify({
                "response": format_gemini_response(response.text),
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
            user_data = get_user_data(user_id)
            user_name = user_data.get('name', 'User')

            def update_tasks(user_data):
                for goal in user_data.get('goals', []):
                    if goal['id'] == goal_id:
                        for task in goal.get('tasks', []):
                            try:
                                detail_prompt = f"""User's Name: {user_name}
For the task: {task['text']}
Provide exactly in this format:
CONTEXT: (write a brief explanation why this task matters)
IMPORTANCE: (just a number 1-100)"""
                                detail_response = model.generate_content(detail_prompt)
                                if detail_response and detail_response.text:
                                    context_match = re.search(r"CONTEXT:\s*(.+?)(?=\n*IMPORTANCE:|$)", detail_response.text, re.DOTALL)
                                    importance_match = re.search(r"IMPORTANCE:\s*(\d+)", detail_response.text)
                                    if context_match:
                                        task['context'] = format_gemini_response(context_match.group(1).strip())
                                    else:
                                        task['context'] = "Task context not available"
                                    if importance_match:
                                        task['importance'] = importance_match.group(1)
                                    else:
                                        task['importance'] = "50"
                                else:
                                    task['context'] = "Task context not available"
                                    task['importance'] = "50"
                                task['isGenerating'] = False
                                logging.info(f"Generated details for task: {task['text']}")
                                time.sleep(0.5)
                            except Exception as task_error:
                                logging.error(f"Error generating details for task '{task['text']}': {task_error}", exc_info=True)
                                task['isGenerating'] = False
                                task['error'] = True
                                task['context'] = "Failed to generate context"
                                task['importance'] = "50"
                        break
            update_user_data(user_id, update_tasks)
            if goal_id in task_detail_events:
                task_detail_events[goal_id].set()
        except Exception as e:
            logging.error(f"Background task error: {e}", exc_info=True)
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
    return jsonify({'isComplete': is_complete, 'goalId': goal_id})

@app.route('/goals', methods=['GET'])
@login_required
def get_goals():
    user = get_user_data(session['user_id'])
    return jsonify(user.get('goals', []))

@app.route('/task', methods=['PUT'])
@login_required
def update_task():
    try:
        data = request.get_json() or {}
        task_id = data.get('taskId')
        completed = data.get('completed')
        db = get_db()
        result = db.users.update_one(
            {"id": session['user_id'], "goals.tasks.id": task_id},
            {"$set": {"goals.$[].tasks.$[task].completed": completed, "goals.$[].tasks.$[task].completedAt": datetime.now().isoformat() if completed else None}},
            array_filters=[{"task.id": task_id}]
        )
        if result.modified_count > 0:
            return jsonify({"success": True})
        return jsonify({'success': False, 'message': 'Task not found'}), 404
    except Exception as e:
        logging.error(f"Error updating task status for task ID '{task_id}': {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/goal', methods=['POST'])
@login_required
def add_goal():
    try:
        data = request.get_json() or {}
        goal_text = data.get('goal')
        if not goal_text:
            return jsonify({'success': False, 'message': 'Goal text is required'}), 400
        new_goal = {
            'id': str(uuid.uuid4()),
            'text': goal_text,
            'tasks': [],
            'isGenerated': False
        }
        db = get_db()
        result = db.users.update_one(
            {"id": session['user_id']},
            {"$push": {"goals": new_goal}}
        )
        if result.modified_count > 0:
            return jsonify({"success": True})
        return jsonify({'success': False, 'message': 'User not found'}), 404
    except Exception as e:
        logging.error(f"Error adding new goal: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/task', methods=['POST'])
@login_required
def add_task():
    try:
        data = request.get_json() or {}
        task_data = data.get('task')
        if not task_data or not task_data.get('text'):
            return jsonify({"error": "Task text is required"}), 400
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
        db = get_db()
        user = db.users.find_one({"id": session['user_id']})
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        if not user.get('goals'):
            new_goal = {
                'id': str(uuid.uuid4()),
                'text': 'Tasks',
                'tasks': [new_task],
                'isGenerated': False
            }
            db.users.update_one(
                {"id": session['user_id']},
                {"$set": {"goals": [new_goal]}}
            )
        else:
            db.users.update_one(
                {"id": session['user_id']},
                {"$push": {"goals.$[last].tasks": new_task}},
                array_filters=[{"last.id": user['goals'][-1]['id']}]
            )
        return jsonify({"success": True, "task": new_task})
    except Exception as e:
        logging.error(f"Error adding new task: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    user = get_user_data(session['user_id'])
    if request.method == 'GET':
        return jsonify(user.get('settings', {}))
    settings_data = request.get_json() or {}
    db = get_db()
    result = db.users.update_one(
        {"id": session['user_id']},
        {"$set": {"settings": settings_data}}
    )
    if result.modified_count > 0:
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Failed to save settings'}), 400

@app.route('/generate-ai-settings', methods=['POST'])
@login_required
def generate_ai_settings():
    try:
        data = request.get_json() or {}
        work_description = data.get('workDescription', '')
        user_name = session.get('user_name')
        if not work_description:
            return jsonify({"error": "Work description is required"}), 400
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
        return jsonify({"error": str(e)}), 500

@app.route('/generate-tasks', methods=['POST'])
@login_required
def generate_tasks():
    try:
        data = request.get_json() or {}
        goal_text = data.get('goalText')
        goal_id = data.get('goalId')
        user_name = session.get('user_name')
        if not goal_text or not goal_id:
            return jsonify({"error": "Goal text and ID are required"}), 400
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
            logging.error(f"Gemini failed to generate tasks for goal '{goal_text}'")
            return jsonify({"error": "Failed to generate tasks"}), 500
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
        db = get_db()
        result = db.users.update_one(
            {"id": session['user_id'], "goals.id": goal_id},
            {"$set": {"goals.$.tasks": new_tasks}}
        )
        if result.modified_count > 0:
            return jsonify({"success": True, "tasks": new_tasks})
        return jsonify({'success': False, 'message': 'Goal not found'}), 404
    except Exception as e:
        logging.error(f"Error generating tasks for goal '{goal_text}': {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/generate-task-details', methods=['POST'])
@login_required
def generate_task_details():
    try:
        data = request.get_json() or {}
        task_id = data.get('task_id')
        task_text = data.get('task_text')
        user_name = session.get('user_name')
        if not task_text or not task_id:
            return jsonify({"error": "Task text and ID required"}), 400
        prompt = f"""User's Name: {user_name}
For the task: "{task_text}"
Return EXACTLY in this format:
CONTEXT: [one quick tip in 3-5 words only] just the context without numbers or any other information
IMPORTANCE: [number 1-100]
"""
        response = model.generate_content(prompt)
        response_text = response.text
        context_match = re.search(r"CONTEXT:\s*(.*?)(?=IMPORTANCE:|$)", response_text, re.DOTALL)
        importance_match = re.search(r"IMPORTANCE:\s*(\d+)", response_text)
        context = context_match.group(1).strip() if context_match else ""
        importance = importance_match.group(1) if importance_match else "50"
        db = get_db()
        result = db.users.update_one(
            {"id": session['user_id'], "goals.tasks.id": task_id},
            {"$set": {"goals.$[].tasks.$[task].context": format_gemini_response(context), "goals.$[].tasks.$[task].importance": importance}},
            array_filters=[{"task.id": task_id}]
        )
        if result.modified_count > 0:
            return jsonify({"success": True, "context": context, "importance": importance})
        return jsonify({'success': False, 'message': 'Task not found'}), 404
    except Exception as e:
        logging.error(f"Error generating task details for task '{task_text}': {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/task/<task_id>', methods=['DELETE'])
@login_required
def delete_task(task_id):
    try:
        db = get_db()
        result = db.users.update_one(
            {"id": session['user_id'], "goals.tasks.id": task_id},
            {"$pull": {"goals.$[].tasks": {"id": task_id}}}
        )
        if result.modified_count > 0:
            return jsonify({"success": True})
        return jsonify({'success': False, 'message': 'Task not found'}), 404
    except Exception as e:
        logging.error(f"Error deleting task with ID '{task_id}': {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/update-task', methods=['POST'])
@login_required
def update_task_details():
    try:
        data = request.get_json() or {}
        task_id = data.get('taskId')
        task_text = data.get('text')
        due_date = data.get('dueDate')
        context = data.get('context')
        importance = data.get('importance')
        if not task_id:
            return jsonify({"error": "Task ID is required"}), 400
        db = get_db()
        result = db.users.update_one(
            {"id": session['user_id'], "goals.tasks.id": task_id},
            {"$set": {
                "goals.$[].tasks.$[task].text": task_text,
                "goals.$[].tasks.$[task].due_date": due_date,
                "goals.$[].tasks.$[task].context": context,
                "goals.$[].tasks.$[task].importance": importance
            }},
            array_filters=[{"task.id": task_id}]
        )
        if result.modified_count > 0:
            return jsonify({"success": True})
        return jsonify({"error": "Task not found"}), 404
    except Exception as e:
        logging.error(f"Error updating task details for task ID '{task_id}': {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

def get_task_category(due_date):
    if not due_date:
        return "today"
    try:
        due_date = datetime.strptime(due_date, '%Y-%m-%d').date()
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        if due_date < today:
            return "today"
        elif due_date == today:
            return "today"
        elif due_date == tomorrow:
            return "tomorrow"
        else:
            return "future"
    except (ValueError, TypeError):
        return "today"

@app.route('/tasks/categorized', methods=['GET'])
@login_required
def get_categorized_tasks():
    user = get_user_data(session['user_id'])
    categorized_tasks = {"today": [], "tomorrow": [], "future": []}
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
        for task in ai_tasks + manual_tasks:
            category = get_task_category(task.get('due_date'))
            categorized_tasks[category].append(task)
    return jsonify(categorized_tasks)

@app.route('/tasks/completed', methods=['GET'])
@login_required
def get_completed_tasks():
    user = get_user_data(session['user_id'])
    completed_tasks = []
    if user.get('goals'):
        latest_goal = user['goals'][-1]
        completed_tasks = [task for task in latest_goal.get('tasks', []) if task.get('completed')]
    return jsonify(completed_tasks)

@app.route('/task/move', methods=['POST'])
@login_required
def move_task():
    try:
        data = request.get_json() or {}
        task_id = data.get('taskId')
        new_date = data.get('newDate')
        db = get_db()
        result = db.users.update_one(
            {"id": session['user_id'], "goals.tasks.id": task_id},
            {"$set": {"goals.$[].tasks.$[task].due_date": new_date}},
            array_filters=[{"task.id": task_id}]
        )
        if result.modified_count > 0:
            return jsonify({"success": True})
        return jsonify({'success': False, 'message': 'Task not found'}), 404
    except Exception as e:
        logging.error(f"Error moving task with ID '{task_id}': {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

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
    db = get_db()
    search_term = request.args.get('search', '').lower()
    users_data = []
    users = db.users.find({}, {"_id": 0, "password": 0})
    for user in users:
        if search_term in user['name'].lower() or search_term in user['email'].lower():
            users_data.append({"id": user['id'], "name": user['name'], "email": user['email'], "settings": user.get('settings', {})})
    return jsonify(users_data)

@app.route('/tasks/all', methods=['GET'])
@login_required
@admin_required
def get_all_tasks_admin():
    db = get_db()
    all_tasks = []
    search_term = request.args.get('search', '').lower()
    users = db.users.find({}, {"_id": 0, "password": 0})
    for user in users:
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
    db = get_db()
    user_data = db.users.find_one({"id": user_id}, {"_id": 0})
    if not user_data:
        return jsonify({'message': 'User not found'}), 404
    user_tasks = []
    user_goals = user_data.get('goals', [])
    user_settings = user_data.get('settings', {})
    for goal in user_goals:
        for task in goal.get('tasks', []):
            task_with_goal = {
                **task,
                'goalId': goal['id'],
                'goalName': goal['text']
            }
            user_tasks.append(task_with_goal)
    user_details = {
        'user': {"id": user_data['id'], "name": user_data['name'], "email": user_data['email'], "settings": user_settings},
        'tasks': user_tasks,
        'goals': user_goals
    }
    return jsonify(user_details)

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    try:
        return render_template('admin_dashboard.html')
    except Exception as e:
        return jsonify({"error": "Rendering templates may not work on Vercel without static setup", "details": str(e)}), 500

def check_due_tasks():
    now = datetime.now()
    tomorrow = now + timedelta(days=1)
    db = get_db()
    users = db.users.find({}, {"_id": 0})
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
    return notifications

def generate_task_dependencies(tasks):
    dependencies = []
    for i, task in enumerate(tasks):
        if i > 0:
            prompt = f"""User's Name: {session.get('user_name')}
Given these two tasks:
{tasks[i-1]['text']}
{task['text']}
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
Work description: {settings.get('workDescription')}
Completed tasks: {', '.join(completed_tasks)}
Suggest 3 new tasks that would be logical next steps.
Return only the tasks, one per line."""
    try:
        response = model.generate_content(prompt)
        return [task.strip() for task in response.text.split('\n') if task.strip()]
    except Exception as e:
        logging.error(f"Error generating task suggestions for user ID '{user_id}': {e}", exc_info=True)
        return []

# Vercel handler for serverless deployment
def handler(event, context):
    from wsgi import wsgi_handler
    return wsgi_handler(app, event, context)

if __name__ == '__main__':
    app.run(host='0.0.0.0')
