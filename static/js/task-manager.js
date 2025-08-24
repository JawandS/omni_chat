/**
 * Task Management JavaScript Module
 * Handles all task-related functionality including CRUD operations,
 * modal management, and task list rendering.
 */

class TaskManager {
    constructor() {
        this.tasks = [];
        this.currentEditingTask = null;
        this.initializeElements();
        this.attachEventListeners();
    }

    initializeElements() {
        // Modal elements
        this.taskModal = document.getElementById('task-modal');
        this.taskForm = document.getElementById('task-form');
        this.saveTaskBtn = document.getElementById('save-task');
        this.taskOutputSelect = document.getElementById('task-output');
        this.emailField = document.getElementById('email-field');
        
        // List elements
        this.taskList = document.getElementById('task-list');
        this.taskCount = document.getElementById('task-count');
        
        // Filter elements
        this.filterStatus = document.getElementById('filter-status');
        this.filterFrequency = document.getElementById('filter-frequency');
    }

    attachEventListeners() {
        // Modal controls
        this.taskModal?.querySelectorAll('[data-close-task]')?.forEach(btn => 
            btn.addEventListener('click', () => this.closeModal())
        );
        
        // Save task button
        this.saveTaskBtn?.addEventListener('click', (e) => this.saveTask(e));
        
        // Output type change
        this.taskOutputSelect?.addEventListener('change', () => this.toggleEmailField());
        
        // Filter changes
        this.filterStatus?.addEventListener('change', () => this.renderTasks());
        this.filterFrequency?.addEventListener('change', () => this.renderTasks());
        
        // Form submit prevention
        this.taskForm?.addEventListener('submit', (e) => e.preventDefault());
    }

    async loadTasks() {
        try {
            const response = await fetch('/api/tasks');
            if (!response.ok) throw new Error('Failed to load tasks');
            
            const data = await response.json();
            this.tasks = data.tasks || [];
            this.renderTasks();
        } catch (error) {
            console.error('Error loading tasks:', error);
            this.showError('Failed to load tasks');
        }
    }

    renderTasks() {
        if (!this.taskList || !this.taskCount) return;
        
        const filteredTasks = this.filterTasks();
        this.taskCount.textContent = `${filteredTasks.length} task${filteredTasks.length !== 1 ? 's' : ''}`;
        
        if (filteredTasks.length === 0) {
            this.taskList.innerHTML = this.getEmptyStateHTML();
            return;
        }
        
        this.taskList.innerHTML = filteredTasks.map(task => this.getTaskHTML(task)).join('');
    }

    filterTasks() {
        const statusFilter = this.filterStatus?.value || 'all';
        const frequencyFilter = this.filterFrequency?.value || 'all';
        
        return this.tasks.filter(task => {
            const statusMatch = statusFilter === 'all' || task.status === statusFilter;
            const frequencyMatch = frequencyFilter === 'all' || task.frequency === frequencyFilter;
            return statusMatch && frequencyMatch;
        });
    }

    getEmptyStateHTML() {
        return `
            <div class="text-center py-12 text-white/60">
                <div class="text-4xl mb-3">📅</div>
                <p class="text-lg mb-2">No scheduled tasks yet</p>
                <p class="text-sm">Create your first task to get started with AI automation</p>
                <button onclick="window.taskManager.openModal()" class="mt-4 px-4 py-2 bg-primary-600 hover:bg-primary-500 rounded-lg text-sm font-medium transition-all">
                    Create First Task
                </button>
            </div>
        `;
    }

    getTaskHTML(task) {
        return `
            <div class="bg-white/5 rounded-xl border border-white/10 p-4">
                <div class="flex items-start justify-between mb-3">
                    <div>
                        <h3 class="font-semibold text-lg">${this.escapeHtml(task.name)}</h3>
                        <p class="text-sm text-white/70 mt-1">${this.escapeHtml(task.description)}</p>
                    </div>
                    <div class="flex items-center space-x-2">
                        <span class="px-2 py-1 text-xs rounded-full ${this.getStatusColor(task.status)} font-medium">
                            ${task.status.charAt(0).toUpperCase() + task.status.slice(1)}
                        </span>
                        <button onclick="window.taskManager.copyTask(${task.id})" class="text-blue-400 hover:text-blue-300 text-sm" title="Copy Task">
                            📋
                        </button>
                        <button onclick="window.taskManager.editTask(${task.id})" class="text-yellow-400 hover:text-yellow-300 text-sm" title="Edit Task">
                            ✏️
                        </button>
                        <button onclick="window.taskManager.deleteTask(${task.id})" class="text-red-400 hover:text-red-300 text-sm" title="Delete Task">
                            🗑️
                        </button>
                    </div>
                </div>
                
                <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                        <span class="text-white/50">Next Run:</span>
                        <div class="font-medium">${this.formatDateTime(task.date, task.time)}</div>
                    </div>
                    <div>
                        <span class="text-white/50">Frequency:</span>
                        <div class="font-medium">${task.frequency === 'none' ? 'One-time' : task.frequency.charAt(0).toUpperCase() + task.frequency.slice(1)}</div>
                    </div>
                    <div>
                        <span class="text-white/50">Provider:</span>
                        <div class="font-medium">${task.provider.toUpperCase()} (${task.model})</div>
                    </div>
                    <div>
                        <span class="text-white/50">Output:</span>
                        <div class="font-medium">${task.output === 'application' ? 'Application' : `Email (${task.email || 'N/A'})`}</div>
                    </div>
                </div>
            </div>
        `;
    }

    openModal(taskData = null) {
        if (!this.taskModal) return;
        
        this.currentEditingTask = taskData;
        this.taskModal.classList.remove('hidden');
        
        if (taskData) {
            // Editing existing task
            this.populateForm(taskData);
            this.saveTaskBtn.textContent = 'Update Task';
        } else {
            // Creating new task
            this.taskForm?.reset();
            this.toggleEmailField();
            this.saveTaskBtn.textContent = 'Create Task';
            
            // Set default date to today
            const today = new Date().toISOString().split('T')[0];
            const dateInput = document.getElementById('task-date');
            if (dateInput) dateInput.value = today;
        }
    }

    closeModal() {
        if (!this.taskModal) return;
        
        this.taskModal.classList.add('hidden');
        this.taskForm?.reset();
        this.toggleEmailField();
        this.currentEditingTask = null;
    }

    populateForm(task) {
        const fields = [
            'task-name', 'task-description', 'task-date', 'task-time',
            'task-frequency', 'task-provider', 'task-model', 'task-output'
        ];
        
        fields.forEach(fieldId => {
            const element = document.getElementById(fieldId);
            const fieldName = fieldId.replace('task-', '');
            if (element && task[fieldName] !== undefined) {
                element.value = task[fieldName];
            }
        });
        
        const emailInput = document.getElementById('task-email');
        if (emailInput && task.email) {
            emailInput.value = task.email;
        }
        
        this.toggleEmailField();
    }

    toggleEmailField() {
        if (!this.taskOutputSelect || !this.emailField) return;
        
        const emailInput = document.getElementById('task-email');
        if (this.taskOutputSelect.value === 'email') {
            this.emailField.classList.remove('hidden');
            if (emailInput) emailInput.required = true;
        } else {
            this.emailField.classList.add('hidden');
            if (emailInput) emailInput.required = false;
        }
    }

    async saveTask(e) {
        e.preventDefault();
        
        if (!this.taskForm?.checkValidity()) {
            this.taskForm?.reportValidity();
            return;
        }
        
        const taskData = this.getFormData();
        
        try {
            let response;
            if (this.currentEditingTask) {
                // Update existing task
                response = await fetch(`/api/tasks/${this.currentEditingTask.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(taskData)
                });
            } else {
                // Create new task
                response = await fetch('/api/tasks', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(taskData)
                });
            }
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to save task');
            }
            
            this.closeModal();
            await this.loadTasks();
            this.showSuccess(this.currentEditingTask ? 'Task updated successfully!' : 'Task created successfully!');
        } catch (error) {
            console.error('Error saving task:', error);
            this.showError(error.message);
        }
    }

    getFormData() {
        return {
            name: document.getElementById('task-name')?.value,
            description: document.getElementById('task-description')?.value,
            date: document.getElementById('task-date')?.value,
            time: document.getElementById('task-time')?.value,
            frequency: document.getElementById('task-frequency')?.value,
            provider: document.getElementById('task-provider')?.value,
            model: document.getElementById('task-model')?.value,
            output: document.getElementById('task-output')?.value,
            email: document.getElementById('task-email')?.value
        };
    }

    async copyTask(taskId) {
        try {
            const response = await fetch(`/api/tasks/${taskId}/copy`, {
                method: 'POST'
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to copy task');
            }
            
            await this.loadTasks();
            this.showSuccess('Task copied successfully!');
        } catch (error) {
            console.error('Error copying task:', error);
            this.showError(error.message);
        }
    }

    async editTask(taskId) {
        try {
            const response = await fetch(`/api/tasks/${taskId}`);
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to load task');
            }
            
            const data = await response.json();
            this.openModal(data.task);
        } catch (error) {
            console.error('Error loading task for edit:', error);
            this.showError(error.message);
        }
    }

    async deleteTask(taskId) {
        if (!confirm('Are you sure you want to delete this task?')) return;
        
        try {
            const response = await fetch(`/api/tasks/${taskId}`, {
                method: 'DELETE'
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to delete task');
            }
            
            await this.loadTasks();
            this.showSuccess('Task deleted successfully!');
        } catch (error) {
            console.error('Error deleting task:', error);
            this.showError(error.message);
        }
    }

    // Utility methods
    getStatusColor(status) {
        switch (status) {
            case 'pending': return 'bg-yellow-600/20 text-yellow-400';
            case 'running': return 'bg-blue-600/20 text-blue-400';
            case 'completed': return 'bg-green-600/20 text-green-400';
            case 'failed': return 'bg-red-600/20 text-red-400';
            default: return 'bg-gray-600/20 text-gray-400';
        }
    }

    formatDateTime(date, time) {
        try {
            const dateObj = new Date(`${date}T${time}`);
            return dateObj.toLocaleDateString() + ' ' + dateObj.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        } catch {
            return `${date} ${time}`;
        }
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    showSuccess(message) {
        // You can implement a toast notification system here
        console.log('Success:', message);
        // For now, just alert
        alert(message);
    }

    showError(message) {
        // You can implement a toast notification system here
        console.error('Error:', message);
        // For now, just alert
        alert(`Error: ${message}`);
    }
}

// Initialize task manager when DOM is loaded
if (typeof window !== 'undefined') {
    window.addEventListener('DOMContentLoaded', () => {
        if (window.location.pathname === '/schedule') {
            window.taskManager = new TaskManager();
            window.taskManager.loadTasks();
        }
    });
}

// Global function for backward compatibility
window.openTaskModal = function() {
    if (window.taskManager) {
        window.taskManager.openModal();
    }
};
