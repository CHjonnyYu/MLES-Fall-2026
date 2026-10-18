/* Published CMS records extend the versioned teaching material on the portal. */
(async () => {
  try {
    const response = await fetch('/api/catalog', { credentials: 'same-origin', cache: 'no-store' });
    if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) return;
    const catalog = await response.json();
    const safeLink = value => typeof value === 'string' && (value.startsWith('https://') || (value.startsWith('/') && !value.startsWith('//')));
    for (const week of catalog.weeks) {
      const section = document.getElementById(`week-${week.number}`);
      const row = document.querySelector(`.schedule-row a[href="#week-${week.number}"]`);
      if (!section) continue;
      section.querySelector('summary span').textContent = week.title;
      section.querySelector('summary small').textContent = `W${week.number} · ${new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', timeZone: 'UTC' }).format(new Date(`${week.date}T12:00:00Z`))}`;
      section.querySelector('.week-body > p').textContent = week.focus;
      if (row) {
        row.textContent = week.title;
        const time = row.parentElement.querySelector('time');
        time.dateTime = week.date;
        time.textContent = new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${week.date}T12:00:00Z`));
        row.parentElement.querySelector('.phase').textContent = week.phase;
      }
      if (!week.resources.length) continue;
      const container = document.createElement('div');
      container.className = 'managed-resources';
      const heading = document.createElement('h4');
      heading.textContent = 'Additional course resources';
      container.append(heading);
      for (const item of week.resources) {
        if (!safeLink(item.url)) continue;
        const resource = document.createElement('section'); resource.className = 'resource';
        const title = document.createElement('h4'); title.textContent = item.title;
        const description = document.createElement('p'); description.textContent = item.description;
        const actions = document.createElement('div'); actions.className = 'actions';
        const link = document.createElement('a'); link.href = item.url; link.textContent = `Open ${item.kind}`; link.target = '_blank'; link.rel = 'noreferrer';
        actions.append(link);
        if (safeLink(item.colab_url)) {
          const colab = document.createElement('a'); colab.href = item.colab_url; colab.textContent = 'Open in Colab'; colab.className = 'button colab'; colab.target = '_blank'; colab.rel = 'noreferrer'; actions.append(colab);
        }
        resource.append(title, description, actions); container.append(resource);
      }
      section.querySelector('.week-body').append(container);
    }
  } catch (_) {
    // The static course remains readable offline; edits load when the API is available.
  }
})();
