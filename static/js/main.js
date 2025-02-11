const chatMessages = document.getElementById('chatMessages');
const chatInput = document.getElementById('chatInput');
const taskContainer = document.getElementById('taskContainer');
const taskList = document.getElementById('taskList');
const modalCompletedTaskList = document.getElementById('modalCompletedTaskList');
const completedTaskModal = document.getElementById('completedTaskModal');
const taskDetailsModal = document.getElementById('taskDetailsModal');
const taskDetailsId = document.getElementById('taskDetailsId');
const taskDetailsText = document.getElementById('taskDetailText');
const taskDetailsDueDate = document.getElementById('taskDetailDueDate');
const taskDetailsContext = document.getElementById('taskDetailContext');
const taskDetailsImportance = document.getElementById('taskDetailImportance');
const addTaskModal = document.getElementById('addTaskModal');
const addTaskText = document.getElementById('addTaskText');
const addTaskDueDate = document.getElementById('addTaskDueDate');
const addTaskContext = document.getElementById('addTaskContext');
const addTaskImportance = document.getElementById('addTaskImportance');
const settingsModal = document.getElementById('settingsModal');
const workDescription = document.getElementById('workDescription');
const shortTermFocus = document.getElementById('shortTermFocus');
const longTermGoals = document.getElementById('longTermGoals');
const sortingPreferences = document.getElementById('sortingPreferences');
let cachedGoals = null;
let showCompletedTasks = false;
let chatInputTimeout = null;
let activeModal = null;

flatpickr("#taskDetailsDueDate", {
    dateFormat: "Y-m-d",
});

flatpickr("#addTaskDueDate", {
    dateFormat: "Y-m-d",
});

function toggleCompletedTasks(event) {
    if (event) {
        event.stopPropagation();
    }

    if (activeModal === completedTaskModal) {
        closeModal(completedTaskModal);
        activeModal = null;
    } else {
        if (activeModal) {
            closeModal(activeModal);
        }
        openModal(completedTaskModal);
        renderCompletedTasks();
        activeModal = completedTaskModal;
    }
}

function openModal(modal) {
    modal.classList.add('show');
    document.body.style.overflow = 'hidden';
}

function closeModal(modal) {
    modal.classList.remove('show');
    document.body.style.overflow = '';
}

// Update close button handlers
document.querySelectorAll('.close-button').forEach(button => {
    button.onclick = function(e) {
        e.stopPropagation();
        const modal = this.closest('.modal');
        if (modal) {
            closeModal(modal);
            activeModal = null;
        }
    };
});

// Close modal when clicking outside
document.querySelectorAll('.modal').forEach(modal => {
    modal.onclick = function(e) {
        if (e.target === this) {
            closeModal(this);
            activeModal = null;
        }
    };
});

// Close modal with Escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && activeModal) {
        closeModal(activeModal);
        activeModal = null;
    }
});

function toggleAddTaskModal() {
    const modal = document.getElementById('addTaskModal');
    if (modal.classList.contains('show')) {
        closeAddTaskModal();
    } else {
        if (activeModal) {
            closeModal(activeModal);
        }
        openModal(modal);
        activeModal = modal;
    }
}

async function toggleSettingsModal() {
    const modal = document.getElementById('settingsModal');
    if (modal.classList.contains('show')) {
        closeSettingsModal();
    } else {
        if (activeModal) {
            closeModal(activeModal);
        }
        openModal(modal);
        try {
            const response = await fetch('/settings', {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });
            if (!response.ok) {
                throw new Error('Failed to get settings');
            }
            const data = await response.json();

            workDescription.value = data.workDescription || '';
            shortTermFocus.value = data.shortTermFocus || '';
            longTermGoals.value = data.longTermGoals || '';
            sortingPreferences.value = data.sortingPreferences || '';

        } catch (error) {
            console.error('Error loading settings:', error);
            addMessage('Failed to load settings. Please try again later.', 'error');
        }
        activeModal = modal;
    }
}

function closeAddTaskModal() {
    addTaskModal.classList.remove('show');
    document.body.style.overflow = '';
}

function closeSettingsModal() {
    settingsModal.classList.remove('show');
    document.body.style.overflow = '';
}

function closeTaskDetailsModal() {
    const modal = document.getElementById('taskDetailsModal');
    modal.classList.remove('show');
    document.body.style.overflow = '';

    // Remove the event listener to prevent duplicates
    const importanceSlider = document.getElementById('taskDetailImportance');
    importanceSlider.removeEventListener('input', null);
}

async function saveSettings() {
    const settingsData = {
        workDescription: workDescription.value,
        shortTermFocus: shortTermFocus.value,
        longTermGoals: longTermGoals.value,
        sortingPreferences: sortingPreferences.value
    }
    try {
        const response = await fetch('/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settingsData)
        });

        if (!response.ok) {
            throw new Error('Failed to save settings');
        }

        closeSettingsModal();
    } catch (error) {
        console.error('Error:', error);
        addMessage('Failed to save settings. Please try again later.', 'error');
    }
}

async function generateAISettings() {
    const workDesc = workDescription.value.trim();
    if (!workDesc) {
        alert('Please add a work description first.');
        return;
    }

    try {
        // Show loading state - Fix the button selector
        const generateButton = document.querySelector('button[onclick="generateAISettings()"]');
        // Or alternatively:
        // const generateButton = document.querySelector('.modal-buttons button:first-child');

        if (!generateButton) {
            console.error('Generate button not found');
            return;
        }

        const originalText = generateButton.textContent;
        generateButton.textContent = 'Generating...';
        generateButton.disabled = true;

        const response = await fetch('/generate-ai-settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ workDescription: workDesc })
        });

        if (!response.ok) {
            throw new Error('Failed to generate settings');
        }

        const data = await response.json();
        shortTermFocus.value = data.shortTermFocus;
        longTermGoals.value = data.longTermGoals;
        sortingPreferences.value = data.sortingPreferences;

        // Reset button state
        generateButton.textContent = originalText;
        generateButton.disabled = false;

    } catch (error) {
        console.error('Error Generating AI Settings:', error);
        const generateButton = document.querySelector('button[onclick="generateAISettings()"]');
        if (generateButton) {
            generateButton.textContent = 'Generate with AI';
            generateButton.disabled = false;
        }
        alert('Failed to generate settings.');
    }
}

async function addNewTask() {
    const taskText = addTaskText.value.trim();
    const dueDate = addTaskDueDate.value;
    const context = addTaskContext.value.trim();

    if (!taskText) {
        alert('Please add task text.');
        return;
    }

    try {
        // Create the task with basic details
        const taskData = {
            text: taskText,
            dueDate: dueDate,
            context: context
        };

        // If context is not provided, get AI-generated details
        if (!context) {
            try {
                const detailsResponse = await fetch('/generate-task-details', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ task_text: taskText })
                });

                if (detailsResponse.ok) {
                    const details = await detailsResponse.json();
                    taskData.context = details.context;
                    taskData.importance = details.importance;
                }
            } catch (error) {
                console.warn('Failed to generate AI details, using defaults');
                taskData.importance = '50';
            }
        }

        // Add the task
        const response = await fetch('/task', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                task: taskData
            })
        });

        if (!response.ok) {
            throw new Error('Failed to add task');
        }

        await loadCategorizedTasks();
        closeAddTaskModal();
        addTaskText.value = '';
        addTaskDueDate.value = '';
        addTaskContext.value = '';

    } catch (error) {
        console.error('Error:', error);
        alert('Failed to add task. Please try again later.');
    }
}

function addMessage(message, type) {
    const messageElement = document.createElement('div');
    messageElement.className = `message ${type}-message`;
    messageElement.textContent = message;
    chatMessages.appendChild(messageElement);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function renderGoals(goals) {
    taskList.innerHTML = ''; // Clear existing content
    if (!goals || goals.length === 0) {
        const emptyGoals = document.createElement('div');
        emptyGoals.className = 'empty-state';
        emptyGoals.innerHTML = '<p>No goals yet. Ask me to help with a goal!</p>';
        taskList.appendChild(emptyGoals);
        return;
    }

    // Get the latest goal (last one in the array)
    const latestGoal = goals[goals.length - 1];

    const goalSection = document.createElement('div');
    goalSection.className = 'goal-section';
    goalSection.innerHTML = `
        <div class="goal-header">
            <h3>${latestGoal.text}</h3>
        </div>
        <div class="task-list task-list-${latestGoal.id}">
        </div>
    `;
    taskList.appendChild(goalSection);

    // Sort tasks by creation time (newest first)
    const sortedTasks = latestGoal.tasks ? [...latestGoal.tasks].reverse() : [];
    renderTasks(sortedTasks, `task-list-${latestGoal.id}`);

    // Scroll to top to show newest tasks
    taskList.scrollTop = 0;
}

function renderTasks(tasks, taskListId) {
    const taskListElement = document.querySelector(`.${taskListId}`);
    taskListElement.innerHTML = '';

    if (!tasks || tasks.length === 0) {
        const emptyTasks = document.createElement('div');
        emptyTasks.className = 'empty-state';
        emptyTasks.innerHTML = '<p>No tasks yet.</p>';
        taskListElement.appendChild(emptyTasks);
        return;
    }

    tasks.forEach(task => {
        const taskItem = document.createElement('div');
        taskItem.className = `task-item ${task.completed ? 'completed' : ''}`;
        taskItem.dataset.taskId = task.id;
        taskItem.dataset.context = task.context || '';
        taskItem.dataset.importance = task.importance || '50';

        // Add progress indicator
        const importance = parseInt(task.importance);
        const priorityClass = importance > 75 ? 'high' : importance > 50 ? 'medium' : 'low';
        taskItem.dataset.importance = priorityClass;

        taskItem.innerHTML = `
            <div class="task-content">
                <input type="checkbox"
                       ${task.completed ? 'checked' : ''}
                       onclick="toggleTask('${task.id}', event)">
                <div class="task-details">
                    <span class="task-text">${task.text}</span>
                    <div class="task-progress">
                        <div class="progress-bar" style="width: ${importance}%"></div>
                    </div>
                </div>
            </div>
        `;

        // Add click handler for task details
        taskItem.addEventListener('click', (e) => {
            if (!e.target.matches('input[type="checkbox"]')) {
                showTaskDetails(task);
            }
        });

        taskListElement.appendChild(taskItem);
    });
}

function showTaskDetails(task) {
    const modal = document.getElementById('taskDetailsModal');
    const taskId = document.getElementById('taskDetailsId');
    const taskText = document.getElementById('taskDetailText');
    const taskDetailsDueDate = document.getElementById('taskDetailDueDate');
    const taskDetailsContext = document.getElementById('taskDetailContext');
    const taskDetailsImportance = document.getElementById('taskDetailImportance');
    const deleteTaskButton = document.getElementById('deleteTaskButton'); // Get the delete button

    taskId.value = task.id;
    taskText.value = task.text;
    taskDetailsDueDate.value = task.due_date || ''; // Corrected here
    taskDetailsContext.value = task.context || ''; // Corrected here
    taskDetailsImportance.value = task.importance || 50; // Corrected here

    // Initialize the slider
    updateImportanceSlider(taskDetailsImportance, taskDetailsImportance.value);

    // Add input event listener for real-time updates
    taskDetailsImportance.addEventListener('input', (e) => {
        updateImportanceSlider(e.target, e.target.value);
    });

    // Set up delete button click handler - moved inside showTaskDetails to have access to task.id
    deleteTaskButton.onclick = function() { // Assign function directly to onclick
        deleteTask(task.id);
    };

    openModal(modal);
    activeModal = modal;
}

async function deleteTask(taskId) {
    try {
        const response = await fetch(`/task/${taskId}`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' }
        });

        if (!response.ok) {
            const message = await response.json();
            throw new Error(message.message || 'Failed to delete task');
        }

        closeTaskDetailsModal();
        await loadCategorizedTasks(); // Refresh tasks after deletion
        // removed this line to prevent the success message from showing
        // addMessage('Task deleted successfully.', 'success');

    } catch (error) {
        console.error('Error deleting task:', error);
        addMessage('Failed to delete task. Please try again.', 'error');
    }
}


function updateImportanceSlider(slider, value) {
    const container = slider.closest('.importance-slider-container');
    const displayValue = slider.closest('.task-detail-item').querySelector('.importance-value');

    // Update the value display
    displayValue.textContent = value;

    // Update the progress bar
    const percent = ((value - slider.min) / (slider.max - slider.min)) * 100;
    container.style.setProperty('--slider-value', `${percent}%`);
    container.style.setProperty('--slider-color', getImportanceColor(value));
}

function getImportanceColor(value) {
    if (value < 33) return 'var(--success)';
    if (value < 66) return 'var(--warning)';
    return 'var(--danger)';
}

async function saveTaskDetails() {
    const taskId = document.getElementById('taskDetailsId').value;
    const taskText = document.getElementById('taskDetailText').value;
    const dueDate = document.getElementById('taskDetailsDueDate').value;
    const context = document.getElementById('taskDetailContext').value;
    const importance = document.getElementById('taskDetailsImportance').value;

    if (!taskId || !taskText) {
        console.error('Missing required fields');
        return;
    }

    try {
        console.log('Sending task update:', { taskId, text: taskText, dueDate, context, importance }); // Debug log

        const response = await fetch('/update-task', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                taskId,
                text: taskText,
                dueDate,
                context,
                importance: parseInt(importance)
            })
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || 'Failed to update task');
        }

        // Refresh goals to show updated task
        await loadGoals();
        closeTaskDetailsModal();
    } catch (error) {
        console.error('Error:', error);
        alert('Failed to update task. Please try again.');
    }
}

async function renderCompletedTasks() {
    modalCompletedTaskList.innerHTML = '';

    try {
        const response = await fetch('/tasks/all');
        if (!response.ok) {
            throw new Error('Failed to fetch tasks');
        }

        const tasks = await response.json();
        let completedTasks = tasks.filter(task => task.completed);

        if (completedTasks.length === 0) {
            const emptyTasks = document.createElement('div');
            emptyTasks.className = 'empty-state';
            emptyTasks.innerHTML = '<p>No completed tasks yet.</p>';
            modalCompletedTaskList.appendChild(emptyTasks);
            return;
        }

        completedTasks.forEach(task => {
            const taskItem = document.createElement('div');
            taskItem.className = 'task-item completed';
            taskItem.dataset.taskId = task.id;

            taskItem.innerHTML = `
                <div class="task-content">
                    <input type="checkbox"
                           checked
                           onclick="toggleTask('${task.id}', event)">
                    <span class="task-text">${task.text}</span>
                </div>
            `;

            modalCompletedTaskList.appendChild(taskItem);
        });
    } catch (error) {
        console.error('Error loading completed tasks:', error);
        const errorMessage = document.createElement('div');
        errorMessage.className = 'error-state';
        errorMessage.innerHTML = '<p>Failed to load completed tasks. Please try again.</p>';
        modalCompletedTaskList.appendChild(errorMessage);
    }
}

async function toggleTask(taskId, event) {
    event.stopPropagation();
    const checkbox = event.target;
    const originalState = checkbox.checked;

    try {
        const response = await fetch('/task', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                taskId: taskId,
                completed: checkbox.checked
            })
        });

        if (!response.ok) {
            throw new Error('Failed to update task');
        }

        // If we're in the completed tasks modal and unchecking a task
        if (!checkbox.checked && activeModal === completedTaskModal) {
            // Remove the task item from the completed tasks list
            const taskItem = checkbox.closest('.task-item');
            if (taskItem) {
                taskItem.remove();

                // Check if there are no more completed tasks
                if (modalCompletedTaskList.children.length === 0) {
                    const emptyTasks = document.createElement('div');
                    emptyTasks.className = 'empty-state';
                    emptyTasks.innerHTML = '<p>No completed tasks yet.</p>';
                    modalCompletedTaskList.appendChild(emptyTasks);
                }
            }
        }

        // Refresh the main task list
        await loadGoals();
    } catch (error) {
        // Revert the checkbox state on error
        checkbox.checked = originalState;
        console.error('Error toggling task:', error);
        addMessage('Failed to update task. Please try again later.', 'error');
    }
}

function loadGoalsFromDOM() {
    const goals = [];
    const goalSections = taskList.querySelectorAll('.goal-section');

    goalSections.forEach(goalSection => {
        const goalText = goalSection.querySelector('h3').textContent;
        const goalId = goalSection.querySelector('.task-list').classList[1].split('-')[2];

        const tasks = [];
        const taskItems = goalSection.querySelectorAll('.task-item');

        taskItems.forEach(taskItem => {
            tasks.push({
                id: taskItem.dataset.taskId,
                text: taskItem.querySelector('span').textContent,
                completed: taskItem.classList.contains('completed')
            });
        });
        goals.push({
            id: goalId,
            text: goalText,
            tasks: tasks
        });
    });

    return goals.length > 0 ? goals : null;
}

async function loadGoals() {
    try {
        // Load the categorized tasks instead of all goals
        await loadCategorizedTasks();
    } catch (error) {
        console.error('Error loading goals:', error);
        addMessage('Failed to load goals. Please try again later.', 'error');
    }
}

async function loadCategorizedTasks() {
    try {
        const response = await fetch('/tasks/categorized');
        const data = await response.json();

        // Clear existing tasks
        document.getElementById('todayTasks').innerHTML = '';
        document.getElementById('tomorrowTasks').innerHTML = '';
        document.getElementById('futureTasks').innerHTML = '';

        // Render tasks in their respective categories
        Object.entries(data).forEach(([category, tasks]) => {
            const container = document.getElementById(`${category}Tasks`);
            if (container) {
                tasks.forEach(task => {
                    const taskElement = createTaskElement(task);
                    container.appendChild(taskElement);
                });
            }
        });
    } catch (error) {
        console.error('Error loading categorized tasks:', error);
        throw error; // Propagate error to loadGoals
    }
}

function createTaskElement(task) {
    const taskElement = document.createElement('div');
    taskElement.className = `task-item ${task.completed ? 'completed' : ''}`;
    taskElement.dataset.taskId = task.id;

    // Add progress indicator
    const importance = parseInt(task.importance);
    const priorityClass = importance > 75 ? 'high' : importance > 50 ? 'medium' : 'low';
    taskElement.dataset.importance = priorityClass;

    taskElement.innerHTML = `
        <div class="task-content">
            <input type="checkbox"
                   ${task.completed ? 'checked' : ''}
                   onclick="toggleTask('${task.id}', event)">
            <div class="task-details">
                <span class="task-text">${task.text}</span>
                <div class="task-progress">
                    <div class="progress-bar" style="width: ${importance}%"></div>
                </div>
            </div>
        </div>
    `;

    // Add click handler for task details
    taskElement.addEventListener('click', (e) => {
        if (!e.target.matches('input[type="checkbox"]')) {
            showTaskDetails(task);
        }
    });

    return taskElement;
}

async function sendMessage() {
    const message = chatInput.value.trim();
    if (message) {
        // Clear input
        chatInput.value = '';

        // Remove welcome message if it exists
        const welcomeMessage = document.querySelector('.empty-state');
        if (welcomeMessage) {
            welcomeMessage.remove();
        }

        // Add message to chat
        addMessage(message, 'user');

        // Handle the message
        await handleMessage(message);
    }
}

async function handleMessage(message) {
    try {
        // Check if it's likely a task generation request
        const goalKeywords = ['help me with', 'steps to', 'how to', 'guide to', 'process for'];
        const isGoalRequest = goalKeywords.some(keyword => message.toLowerCase().includes(keyword));

        // If it's a goal request, show loading immediately
        if (isGoalRequest) {
            const loadingMessage = document.createElement('div');
            loadingMessage.className = 'message ai-message loading';
            loadingMessage.innerHTML = `
                <div class="message-content">
                    <p>Generating tasks for you</p>
                    <div class="loading-animation">
                        <span class="dot"></span>
                        <span class="dot"></span>
                        <span class="dot"></span>
                    </div>
                </div>
            `;
            chatMessages.appendChild(loadingMessage);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

        // Make the API request
        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });

        if (!response.ok) {
            throw new Error('Failed to send message');
        }

        const data = await response.json();

        // Remove loading message if it exists
        const loadingMessage = document.querySelector('.message.loading');
        if (loadingMessage) {
            loadingMessage.remove();
        }

        // Add the response message
        addMessage(data.response, 'ai');
        if (data.tasks && data.tasks.length > 0) {
            await loadGoals();  // Refresh goals to show new tasks
        }

        chatMessages.scrollTop = chatMessages.scrollHeight;
    } catch (error) {
        console.error('Error:', error);
        // Remove loading message if it exists
        const loadingMessage = document.querySelector('.message.loading');
        if (loadingMessage) {
            loadingMessage.remove();
        }
        addMessage('Sorry, there was an error processing your message.', 'error');
    }
}

async function addGoal() {
    const goalText = prompt('Enter goal description:');
    if (!goalText) return;

    try {
        const response = await fetch('/goal', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ goal: goalText })
        });

        if (!response.ok) {
            throw new Error('Failed to add goal');
        }

        loadGoals();
    } catch (error) {
        console.error('Error adding goal:', error);
        addMessage('Failed to add goal. Please try again later.', 'error');
    }
}

function toggleChat() {
    const chatContainer = document.querySelector('.chat-container');
    const taskContainer = document.querySelector('.task-container');
    const chatToggleButton = document.getElementById('chatToggleButton');

    chatContainer.classList.toggle('hidden');
    taskContainer.classList.toggle('chat-hidden');

    // You can also change the icon if you want to indicate the state
    if (chatContainer.classList.contains('hidden')) {
        // Icon for showing chat (e.g., a filled chat bubble)
        chatToggleButton.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M8 10h8m-8 0H28m-16 0a2 2 0 11-4 0 2 2 0 014 0zM8 15h8m-8 0H28m-16 0a2 2 0 11-4 0 2 2 0 014 0z" />
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
            </svg>
        `;
    } else {
        // Icon for hiding chat (e.g., the original chat bubble)
        chatToggleButton.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                <path d="M16 11V7a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v4m7 7h4m-4-4h4m-4-4h4"></path>
            </svg>
        `;
    }
}

// Function to handle login form submission
async function loginFormSubmit(event) {
    event.preventDefault(); // Prevent default form submission

    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;

    try {
        const response = await fetch('/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ email, password }),
        });

        if (!response.ok) {
            const errorData = await response.json();
            alert(errorData.message_detail || 'Login failed'); // Show error message
        } else {
            const successData = await response.json();
            if (successData.success) {
                window.location.href = '/'; // Redirect to index page

                // Open settings modal AFTER successful login and redirect
                window.onload = () => { // Wait for the page to fully load after redirect
                    toggleSettingsModal();
                };
            } else {
                alert(successData.message_detail || 'Login failed');
            }
        }
    } catch (error) {
        console.error('Login error:', error);
        alert('Login failed. Please try again later.');
    }
}


// Initial load
document.addEventListener('DOMContentLoaded', () => {
    loadGoals();

    // No longer open settings modal automatically on initial site load

    // Add event listener for Enter key in chat input
    chatInput.addEventListener('keydown', function(event) {
        if (event.key === 'Enter') {
            event.preventDefault();
            sendMessage();
        }
    });

    // Add global keyboard shortcuts
    document.addEventListener('keydown', function(event) {
        // Only trigger if not in an input or textarea
        if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA') {
            return;
        }

        switch (event.key.toLowerCase()) {
            case 't':
                event.preventDefault();
                toggleAddTaskModal();
                break;
            case 'c':
                event.preventDefault();
                toggleCompletedTasks(event);
                break;
            case 's':
                event.preventDefault();
                toggleSettingsModal();
                break;
        }
    });

    // Update click handlers
    updateClickHandlers();

    // Add importance slider event listener
    const importanceSlider = document.getElementById('taskDetailImportance');
    const importanceValue = document.querySelector('.importance-value');

    importanceSlider.addEventListener('input', (e) => {
        importanceValue.textContent = e.target.value;

        // Update the gradient of the track
        const value = (e.target.value - e.target.min) / (e.target.max - e.target.min) * 100;
        e.target.style.background = `linear-gradient(to right, var(--accent) 0%, var(--accent) ${value}%, var(--border) ${value}%, var(--border) 100%)`;
    });
});

// Add this CSS to show keyboard shortcuts in the UI
const style = document.createElement('style');
style.textContent = `
    .icon-wrapper::after {
        content: attr(data-shortcut);
        position: absolute;
        bottom: -20px;
        left: 50%;
        transform: translateX(-50%);
        font-size: 12px;
        color: #666;
        opacity: 0;
        transition: opacity 0.2s;
    }

    .icon-wrapper:hover::after {
        opacity: 1;
    }
`;
document.head.appendChild(style);

// Update click handlers
function updateClickHandlers() {
    // Update the onclick attributes in the HTML
    document.querySelector('[onclick="openAddTaskModal()"]').setAttribute('onclick', 'toggleAddTaskModal()');
    document.querySelector('[onclick="openSettingsModal()"]').setAttribute('onclick', 'toggleSettingsModal()');
}

// Attach loginFormSubmit to your login form's submit event
document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('loginForm'); // Assuming your form has id="loginForm"
    if (loginForm) {
        loginForm.addEventListener('submit', loginFormSubmit);
    }
});
