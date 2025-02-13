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
const taskDetailsContext = document.getElementById('taskDetailsContext');
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

    // Remove the event listener to prevent duplicates (although not strictly necessary here as modal is recreated each time)
    const importanceSlider = document.getElementById('taskDetailImportance');
    if (importanceSlider && importanceSlider.eventListener) { // Check if eventListener property exists
        importanceSlider.removeEventListener('input', importanceSlider.eventListener);
        importanceSlider.eventListener = null; // Clear the property
    }
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
        const taskItem = createTaskElement(task);
        taskListElement.appendChild(taskItem);
    });
}

function createTaskElement(task) {
    const taskElement = document.createElement('div');
    taskElement.className = `task-item ${task.completed ? 'completed' : ''}`;
    taskElement.dataset.taskId = task.id;
    taskElement.draggable = true; // Make draggable

    // Handle loading state
    if (task.isGenerating) {
        taskElement.innerHTML = `
            <div class="task-content">
                <input type="checkbox"
                       ${task.completed ? 'checked' : ''}
                       onclick="toggleTask('${task.id}', event)">
                <div class="task-details">
                    <span class="task-text">${task.text}</span>
                </div>
                <div class="loading-animation inline">
                    <span class="dot"></span>
                    <span class="dot"></span>
                    <span class="dot"></span>
                </div>
            </div>
        `;
    } else {
        // Add progress indicator for completed tasks
        const importance = parseInt(task.importance || '50');
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
    }

    // Add click handler for task details
    taskElement.addEventListener('click', (e) => {
        if (!e.target.matches('input[type="checkbox"]')) {
            showTaskDetails(task);
        }
    });

    taskElement.addEventListener('dragstart', (event) => {
        event.dataTransfer.setData('taskId', task.id); // Store task ID
    });

    return taskElement;
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

    // Store the event listener function for removal later
    const importanceSliderInputHandler = (e) => {
        updateImportanceSlider(e.target, e.target.value);
    };
    taskDetailsImportance.eventListener = importanceSliderInputHandler; // Store it as a property

    // Add input event listener for real-time updates
    taskDetailsImportance.addEventListener('input', taskDetailsImportance.eventListener);


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
    const dueDate = document.getElementById('taskDetailDueDate').value;
    const context = document.getElementById('taskDetailContext').value;
    const importance = document.getElementById('taskDetailImportance').value;

    if (!taskId || !taskText) {
        console.error('Missing required fields');
        return;
    }

    try {
        console.log('saveTaskDetails() function is being called!'); // Debug log - step 1
        console.log('Sending task update:', { taskId, text: taskText, dueDate, context, importance }); // Debug log - step 2

        const response = await fetch('/update-task', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                taskId: taskId,
                text: taskText,
                dueDate: dueDate,
                context: context,
                importance: parseInt(importance)
            })
        });

        if (!response.ok) {
            // Log the error response for debugging on the client-side
            const errorData = await response.json(); // Try to parse JSON error response
            console.error('Server error response:', errorData);
            throw new Error(`Failed to update task. Server responded with status: ${response.status} and message: ${errorData.message || response.statusText}`);
        }

        const result = await response.json(); // Parse JSON success response
        console.log('Task update successful:', result); // Log success response

        // Refresh goals to show updated task
        await loadCategorizedTasks(); // Changed to loadCategorizedTasks
        closeTaskDetailsModal();

    } catch (error) {
        console.error('Error during task update:', error);
        alert('Failed to update task. Please try again.');
        addMessage('Failed to update task details: ' + error.message, 'error'); // Improved error message
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
        await loadCategorizedTasks(); // Changed to loadCategorizedTasks
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

// Add this function to check task details status
async function pollTaskDetails(goalId) {
    try {
        const response = await fetch(`/task-details-status/${goalId}`);
        const data = await response.json();

        if (data.isComplete) {
            // Reload tasks to show updated details
            await loadCategorizedTasks();
            return true;
        }
        return false;
    } catch (error) {
        console.error('Error checking task details status:', error);
        return false;
    }
}

// Modify the handleMessage function to start polling when tasks are generated
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

            // If tasks are being generated with details, start polling
            if (data.isGenerating && data.goalId) {
                // Add a single loading message for task details
                addMessage("I'm now adding more details to each task...", 'ai');

                // Start polling for task details
                const pollInterval = setInterval(async () => {
                    const isComplete = await pollTaskDetails(data.goalId);
                    if (isComplete) {
                        clearInterval(pollInterval);
                        // Update the last message instead of adding a new one
                        const messages = document.querySelectorAll('.message.ai-message');
                        const lastMessage = messages[messages.length - 1];
                        if (lastMessage) {
                            lastMessage.textContent = 'All task details have been added!';
                        }
                    }
                }, 2000); // Check every 2 seconds

                // Stop polling after 30 seconds to prevent infinite polling
                setTimeout(() => {
                    clearInterval(pollInterval);
                }, 30000);
            }
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

// Update the toggleChat function
function toggleChat() {
    const chatContainer = document.querySelector('.chat-container');
    const taskContainer = document.querySelector('.task-container');
    const wasHidden = chatContainer.classList.contains('hidden');

    chatContainer.classList.toggle('hidden');
    taskContainer.classList.toggle('chat-hidden');

    // Store the state in localStorage
    localStorage.setItem('chatHidden', chatContainer.classList.contains('hidden'));

    // Allow time for the transition and then trigger a resize event
    setTimeout(() => {
        window.dispatchEvent(new Event('resize'));
    }, 300);
}

// Update the DOMContentLoaded event listener
document.addEventListener('DOMContentLoaded', () => {
    // Restore chat visibility state
    const chatHidden = localStorage.getItem('chatHidden') === 'true';
    if (chatHidden) {
        const chatContainer = document.querySelector('.chat-container');
        const taskContainer = document.querySelector('.task-container');
        chatContainer.classList.add('hidden');
        taskContainer.classList.add('chat-hidden');

        // Trigger resize event after initial state is set
        setTimeout(() => {
            window.dispatchEvent(new Event('resize'));
        }, 100);
    }

    // Add all keyboard shortcuts
    document.addEventListener('keydown', function(event) {
        // Only trigger if not in an input or textarea
        if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA') {
            return;
        }

        switch (event.key.toLowerCase()) {
            case 'm': // Toggle chat
                event.preventDefault();
                toggleChat();
                break;
            case 't': // Add task
                event.preventDefault();
                toggleAddTaskModal();
                break;
            case 'c': // Completed tasks
                event.preventDefault();
                toggleCompletedTasks();
                break;
            case 's': // Settings
                event.preventDefault();
                toggleSettingsModal();
                break;
        }
    });

    // Add Enter key listener for chat input
    const chatInput = document.getElementById('chatInput');
    if (chatInput) {
        chatInput.addEventListener('keydown', function(event) {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                sendMessage();
            }
        });
    }

    loadCategorizedTasks(); // Load tasks on page load

    const todayTasksContainer = document.getElementById('todayTasks');
    const tomorrowTasksContainer = document.getElementById('tomorrowTasks');
    const futureTasksContainer = document.getElementById('futureTasks');

    // Function to handle dragover - allows dropping
    const allowDrop = (event) => {
        event.preventDefault();
    };

    // Function to handle drop
    const handleDrop = async (event, category) => {
        event.preventDefault();
        const taskId = event.dataTransfer.getData('taskId');
        let newDate = '';

        if (category === 'tomorrow') {
            const tomorrow = new Date();
            tomorrow.setDate(tomorrow.getDate() + 1);
            newDate = tomorrow.toISOString().slice(0, 10); // YYYY-MM-DD format
        } else if (category === 'future') {
            // For 'future', you might want to set a default future date or let the user specify it in the UI.
            // For now, let's set it to a week from now as an example.
            const futureDate = new Date();
            futureDate.setDate(futureDate.getDate() + 7);
            newDate = futureDate.toISOString().slice(0, 10); // YYYY-MM-DD format
        } else if (category === 'today') {
            const today = new Date();
            newDate = today.toISOString().slice(0, 10); // YYYY-MM-DD format
        }

        try {
            const response = await fetch('/task/move', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ taskId: taskId, newDate: newDate })
            });

            if (!response.ok) {
                throw new Error('Failed to move task');
            }

            await loadCategorizedTasks(); // Reload tasks to reflect changes
            

        } catch (error) {
            console.error('Error moving task:', error);
        }
    };

    // Add dragover and drop listeners to each category container
    todayTasksContainer.addEventListener('dragover', allowDrop);
    todayTasksContainer.addEventListener('drop', (event) => handleDrop(event, 'today'));

    tomorrowTasksContainer.addEventListener('dragover', allowDrop);
    tomorrowTasksContainer.addEventListener('drop', (event) => handleDrop(event, 'tomorrow'));

    futureTasksContainer.addEventListener('dragover', allowDrop);
    futureTasksContainer.addEventListener('drop', (event) => handleDrop(event, 'future'));


});
