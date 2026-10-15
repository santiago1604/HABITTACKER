/* HabitTracker - JavaScript común */
(function () {
    'use strict';

    function getCookie(name) {
        const match = document.cookie.split(';').map(c => c.trim()).find(c => c.startsWith(name + '='));
        return match ? decodeURIComponent(match.split('=').slice(1).join('=')) : null;
    }

    function csrfToken() {
        const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
        return (input && input.value) || getCookie('csrftoken');
    }

    async function postJSON(url, payload) {
        const response = await fetch(url, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrfToken(),
            },
            body: JSON.stringify(payload),
        });
        let data = {};
        try { data = await response.json(); } catch (e) { /* respuesta no JSON */ }
        if (!response.ok || data.status !== 'success') {
            throw new Error(data.message || 'Error ' + response.status);
        }
        return data;
    }

    function toast(message, variant) {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
            document.body.appendChild(container);
        }
        const el = document.createElement('div');
        el.className = 'toast align-items-center border-0 text-bg-' + (variant || 'danger');
        el.setAttribute('role', 'alert');
        el.innerHTML = '<div class="d-flex"><div class="toast-body"></div>' +
            '<button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Cerrar"></button></div>';
        el.querySelector('.toast-body').textContent = message;
        container.appendChild(el);
        if (window.bootstrap) {
            const t = new bootstrap.Toast(el, { delay: 3500 });
            el.addEventListener('hidden.bs.toast', () => el.remove());
            t.show();
        }
    }

    /* ----- Marcar / desmarcar hábitos ----- */
    function initHabitCheckboxes() {
        document.addEventListener('change', async function (event) {
            const checkbox = event.target.closest('.habit-checkbox');
            if (!checkbox) return;

            const isChecked = checkbox.checked;
            checkbox.disabled = true;
            try {
                const data = await postJSON(checkbox.dataset.url, { date: checkbox.dataset.date, completed: isChecked });
                document.querySelectorAll('[data-streak-for="' + checkbox.dataset.habitId + '"]').forEach(el => {
                    el.textContent = data.current_streak;
                });
                // Sincroniza otros checkboxes del mismo hábito y día en la página
                document.querySelectorAll('.habit-checkbox[data-habit-id="' + checkbox.dataset.habitId + '"][data-date="' + checkbox.dataset.date + '"]')
                    .forEach(el => { el.checked = isChecked; });
                checkbox.disabled = false;
                document.dispatchEvent(new CustomEvent('habit:toggled', { detail: { checkbox, data } }));
            } catch (error) {
                checkbox.checked = !isChecked;
                toast('No se pudo actualizar el hábito: ' + error.message);
            } finally {
                checkbox.disabled = false;
            }
        });
    }

    /* ----- Reordenar listas arrastrando ----- */
    function initSortableLists() {
        if (!window.Sortable) return;
        document.querySelectorAll('[data-sortable-url]').forEach(list => {
            Sortable.create(list, {
                handle: '.drag-handle',
                animation: 150,
                ghostClass: 'sortable-ghost',
                onEnd: async function (evt) {
                    if (evt.oldIndex === evt.newIndex) return;
                    const ids = Array.from(list.querySelectorAll('[data-id]')).map(el => parseInt(el.dataset.id, 10));
                    const payload = {};
                    payload[list.dataset.sortableKey] = ids;
                    try {
                        await postJSON(list.dataset.sortableUrl, payload);
                    } catch (error) {
                        toast('No se pudo guardar el nuevo orden: ' + error.message);
                    }
                },
            });
        });
    }

    /* ----- Tema claro / oscuro ----- */
    function initThemeToggle() {
        const button = document.getElementById('theme-toggle');
        if (!button) return;
        const icon = button.querySelector('i');
        const apply = theme => {
            document.documentElement.setAttribute('data-bs-theme', theme);
            if (icon) icon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
        };
        apply(document.documentElement.getAttribute('data-bs-theme') || 'light');
        button.addEventListener('click', () => {
            const next = document.documentElement.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
            apply(next);
            try { localStorage.setItem('theme', next); } catch (e) { /* almacenamiento no disponible */ }
        });
    }

    /* ----- Cerrar alertas automáticamente ----- */
    function initAutoDismissAlerts() {
        document.querySelectorAll('.alert-dismissible[data-autodismiss]').forEach(alert => {
            setTimeout(() => {
                if (window.bootstrap && document.body.contains(alert)) {
                    bootstrap.Alert.getOrCreateInstance(alert).close();
                }
            }, 5000);
        });
    }

    /* ----- Confirmaciones simples en formularios ----- */
    function initConfirmForms() {
        document.addEventListener('submit', function (event) {
            const message = event.target.dataset && event.target.dataset.confirm;
            if (message && !window.confirm(message)) event.preventDefault();
        });
    }

    window.HabitTracker = { postJSON, toast, csrfToken };

    document.addEventListener('DOMContentLoaded', function () {
        initHabitCheckboxes();
        initSortableLists();
        initThemeToggle();
        initAutoDismissAlerts();
        initConfirmForms();
    });
})();
