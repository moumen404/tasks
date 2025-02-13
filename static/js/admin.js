document.addEventListener('DOMContentLoaded', function () {
    const searchInput = document.getElementById('searchInput');
    const userTableBody = document.getElementById('userTableBody');
    const userDetailsModal = new bootstrap.Modal(document.getElementById('userDetailsModal'));
    const userDetailsContent = document.getElementById('userDetailsContent');

    function fetchUsers(query = '') {
        let url = '/admin/users';
        if (query) {
            url = `/admin/users/search?q=${query}`;
        }
        fetch(url)
            .then(response => response.json())
            .then(data => {
                populateUserTable(data.users);
            });
    }

    function populateUserTable(users) {
        userTableBody.innerHTML = ''; // Clear existing table rows
        users.forEach(user => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${user.id}</td>
                <td>${user.name}</td>
                <td>${user.email}</td>
                <td>${user.goals_count}</td>
                <td>${user.tasks_count}</td>
                <td>${user.last_login}</td>
                <td>${user.theme}</td>  <!---- New Column Data ---->
                <td>${user.notifications_enabled ? '<i class="fas fa-check text-success"></i>' : '<i class="fas fa-times text-danger"></i>'}</td> <!---- New Column Data with Icons ---->
                <td>${user.is_admin ? 'Yes' : 'No'}</td>
                <td>
                    <button class="btn btn-sm btn-info view-details-btn" data-user-id="${user.id}">View Details</button>
                </td>
            `;
            userTableBody.appendChild(row);
        });

        // Add event listeners to the "View Details" buttons after they are added to the DOM
        attachViewDetailsListeners();
    }

    function attachViewDetailsListeners() {
        document.querySelectorAll('.view-details-btn').forEach(button => {
            button.addEventListener('click', function() {
                const userId = this.dataset.userId;
                fetchUserDetails(userId);
            });
        });
    }

    function fetchUserDetails(userId) {
        fetch('/admin/users') // Re-fetching all users for simplicity, in real app, fetch single user by ID
            .then(response => response.json())
            .then(data => {
                const user = data.users.find(u => u.id === userId);
                if (user) {
                    populateUserDetailsModal(user);
                    userDetailsModal.show();
                } else {
                    console.error('User not found');
                }
            });
    }

    function populateUserDetailsModal(user) {
        let detailsHTML = `
            <h5>User ID: ${user.id}</h5>
            <p><strong>Name:</strong> ${user.name}</p>
            <p><strong>Email:</strong> ${user.email}</p>
            <p><strong>Registration Date:</strong> ${user.registration_date}</p>
            <p><strong>Last Login:</strong> ${user.last_login}</p>
            <p><strong>Admin:</strong> ${user.is_admin ? 'Yes' : 'No'}</p>
            <p><strong>Theme:</strong> ${user.theme}</p>
            <p><strong>Notifications Enabled:</strong> ${user.notifications_enabled ? 'Yes' : 'No'}</p>
            <hr>
            <h6>Goals:</h6>
        `;

        if (user.goals_list && user.goals_list.length > 0) {
            user.goals_list.forEach(goal => {
                detailsHTML += `
                    <div class="card mb-2">
                        <div class="card-body">
                            <h6 class="card-title"><strong>Goal:</strong> ${goal.title}</h6>
                            <p class="card-text"><strong>Deadline:</strong> ${goal.deadline || 'N/A'}</p>
                            <p class="card-text"><strong>Status:</strong> ${goal.status || 'N/A'}</p>
                            <p class="card-text"><strong>Tasks:</strong> ${goal.task_count}</p>
                            ${goal.tasks && goal.tasks.length > 0 ? '<h6>Tasks:</h6><ul>' : ''}
                            ${goal.tasks && goal.tasks.map(task => `<li><strong>Task:</strong> ${task.title} - <strong>Status:</strong> ${task.status || 'N/A'} - <strong>Deadline:</strong> ${task.deadline || 'N/A'} - <strong>Priority:</strong> ${task.priority || 'N/A'}</li>`).join('')}
                            ${goal.tasks && goal.tasks.length > 0 ? '</ul>' : ''}
                        </div>
                    </div>
                `;
            });
        } else {
            detailsHTML += `<p>No goals available.</p>`;
        }

        userDetailsContent.innerHTML = detailsHTML;
    }


    searchInput.addEventListener('input', function () {
        fetchUsers(searchInput.value);
    });

    fetchUsers(); // Initial load of users
});