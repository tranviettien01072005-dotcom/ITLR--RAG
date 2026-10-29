(() => {
  const message = document.getElementById('learning-message');
  async function submit(form, url, body) {
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    message.textContent = 'Đang lưu…';
    try {
      const token = document.querySelector('input[name="_csrf"]')?.value;
      const response = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': token || '' }, body: JSON.stringify(body) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Không thể lưu. Hãy thử lại.');
      window.location.assign('/learning');
    } catch (error) {
      message.textContent = error.message || 'Mất kết nối. Hãy thử lại.';
      message.className = 'alert';
      button.disabled = false;
    }
  }
  const diagnostic = document.getElementById('diagnostic-form');
  diagnostic?.addEventListener('submit', event => {
    event.preventDefault();
    const data = new FormData(diagnostic);
    submit(diagnostic, '/api/learning/diagnostic', { track: diagnostic.dataset.track, goal: data.get('goal'), answers: [0, 1, 2].map(i => Number(data.get(`q${i}`))) });
  });
  document.querySelectorAll('.learning-progress-form').forEach(form => form.addEventListener('submit', event => {
    event.preventDefault();
    const progress = Number(new FormData(form).get('progress'));
    submit(form, '/api/learning/progress', { course_id: Number(form.dataset.courseId), progress, status: progress === 100 ? 'completed' : progress > 0 ? 'in_progress' : 'saved' });
  }));
})();
