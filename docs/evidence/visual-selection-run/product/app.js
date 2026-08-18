document.addEventListener('DOMContentLoaded', () => {
  // --- STATE ---
  let criteria = ['Impact', 'Feasibility', 'Alignment'];
  let options = [];

  // Load from LocalStorage
  const savedCriteria = localStorage.getItem('atelier_criteria');
  const savedOptions = localStorage.getItem('atelier_options');
  if (savedCriteria) criteria = JSON.parse(savedCriteria);
  if (savedOptions) options = JSON.parse(savedOptions);

  // --- DOM ELEMENTS ---
  const criteriaContainer = document.getElementById('criteria-container');
  const addCriterionBtn = document.getElementById('add-criterion-btn');
  const formInitialScores = document.getElementById('form-initial-scores');
  const optionForm = document.getElementById('option-form');
  const optionsGrid = document.getElementById('options-grid');
  const ledgerCountText = document.getElementById('ledger-count-text');
  const leaderName = document.getElementById('leader-name');
  const leaderScore = document.getElementById('leader-score');
  const leaderDesc = document.getElementById('leader-desc');
  const chartBarsContainer = document.getElementById('chart-bars-container');
  const clearBoardBtn = document.getElementById('clear-board-btn');

  // --- SAVE STATE ---
  function saveState() {
    localStorage.setItem('atelier_criteria', JSON.stringify(criteria));
    localStorage.setItem('atelier_options', JSON.stringify(options));
  }

  // --- RENDER CRITERIA INPUTS ---
  function renderCriteria() {
    criteriaContainer.innerHTML = '';
    formInitialScores.innerHTML = '';

    criteria.forEach((crit, index) => {
      // Criteria Config Editor
      const critDiv = document.createElement('div');
      critDiv.className = 'criteria-item';
      critDiv.innerHTML = `
        <input type="text" class="atelier-input" value="${crit}" aria-label="Criterion ${index + 1}" data-index="${index}">
        <button type="button" class="btn-remove-criterion" data-index="${index}" title="Remove Criterion">&times;</button>
      `;
      
      // Listen for inline edits with score key migration
      const input = critDiv.querySelector('input');
      input.addEventListener('change', (e) => {
        const oldName = criteria[index];
        const newName = e.target.value.trim() || `Criterion ${index + 1}`;
        if (oldName !== newName) {
          criteria[index] = newName;
          // Migrate scores
          options.forEach(opt => {
            if (opt.scores[oldName] !== undefined) {
              opt.scores[newName] = opt.scores[oldName];
              delete opt.scores[oldName];
            }
          });
          saveState();
          renderAll();
        }
      });

      // Listen for removal
      const removeBtn = critDiv.querySelector('.btn-remove-criterion');
      removeBtn.addEventListener('click', () => {
        if (criteria.length <= 1) {
          alert('At least one criterion must remain to evaluate options.');
          return;
        }
        const targetCrit = criteria[index];
        if (confirm(`Are you sure you want to remove the criterion "${targetCrit}"? This will delete scores for this criterion across all options.`)) {
          criteria.splice(index, 1);
          options.forEach(opt => {
            delete opt.scores[targetCrit];
          });
          saveState();
          renderAll();
        }
      });

      criteriaContainer.appendChild(critDiv);

      // Initial Score Row in Form
      const scoreRow = document.createElement('div');
      scoreRow.className = 'initial-score-row';
      scoreRow.innerHTML = `
        <span>${crit}</span>
        <div class="studs-container" data-criterion="${crit}">
          ${[1, 2, 3, 4, 5].map(num => `
            <button type="button" class="stud-btn ${num === 3 ? 'active' : ''}" data-val="${num}" aria-label="Score ${num} for ${crit}">${num}</button>
          `).join('')}
        </div>
      `;

      // Handle stud selection inside form
      scoreRow.querySelectorAll('.stud-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          scoreRow.querySelectorAll('.stud-btn').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
        });
      });

      formInitialScores.appendChild(scoreRow);
    });
  }

  // --- ADD CRITERION ---
  addCriterionBtn.addEventListener('click', () => {
    const newCritName = prompt('Enter name for the new criterion:', `Criterion ${criteria.length + 1}`);
    if (newCritName && newCritName.trim()) {
      const cleanedName = newCritName.trim();
      if (criteria.includes(cleanedName)) {
        alert('A criterion with this name already exists.');
        return;
      }
      criteria.push(cleanedName);
      // Initialize default score of 3 for existing options
      options.forEach(opt => {
        opt.scores[cleanedName] = 3;
      });
      saveState();
      renderAll();
    }
  });

  // --- CALCULATE AVERAGE SCORE ---
  function calculateAverage(option) {
    if (criteria.length === 0) return 0;
    let sum = 0;
    criteria.forEach(crit => {
      sum += option.scores[crit] !== undefined ? option.scores[crit] : 3;
    });
    return parseFloat((sum / criteria.length).toFixed(1));
  }

  // --- RENDER OPTIONS GRID ---
  function renderOptions(leaderId) {
    optionsGrid.innerHTML = '';
    ledgerCountText.textContent = `${options.length} Option${options.length === 1 ? '' : 's'} Registered`;

    if (options.length === 0) {
      optionsGrid.innerHTML = `<p style="font-style: italic; color: #6B6255; text-align: center; margin-top: 2rem;">No options registered. Use the panel on the left to inscribe your first option.</p>`;
      return;
    }

    options.forEach(opt => {
      const isLeader = opt.id === leaderId;
      const avg = calculateAverage(opt);
      const card = document.createElement('article');
      card.className = `option-card ${isLeader ? 'is-leader' : ''}`;
      card.setAttribute('aria-label', `Option: ${opt.name}`);

      let scoresHtml = '';
      criteria.forEach(crit => {
        const currentVal = opt.scores[crit] !== undefined ? opt.scores[crit] : 3;
        scoresHtml += `
          <div class="score-row">
            <span class="score-label">${crit}</span>
            <div class="studs-container" data-option-id="${opt.id}" data-criterion="${crit}">
              ${[1, 2, 3, 4, 5].map(num => `
                <button type="button" class="stud-btn ${num === currentVal ? 'active' : ''}" data-val="${num}" aria-label="Set ${crit} to ${num}">${num}</button>
              `).join('')}
            </div>
          </div>
        `;
      });

      card.innerHTML = `
        <div class="card-header">
          <div>
            <h3 class="card-title">${opt.name}</h3>
          </div>
          <div class="card-score-summary">${avg}</div>
        </div>
        <p class="card-desc">${opt.desc || 'No description provided.'}</p>
        <div class="card-scores">
          ${scoresHtml}
        </div>
        <div class="card-actions">
          <button class="btn-delete-card" data-id="${opt.id}">Remove Option</button>
        </div>
      `;

      // Event listeners for inline scoring
      card.querySelectorAll('.stud-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          const optId = btn.parentElement.getAttribute('data-option-id');
          const critName = btn.parentElement.getAttribute('data-criterion');
          const newVal = parseInt(btn.getAttribute('data-val'), 10);
          
          const targetOpt = options.find(o => o.id === optId);
          if (targetOpt) {
            targetOpt.scores[critName] = newVal;
            saveState();
            renderAll();
          }
        });
      });

      // Event listener for delete
      card.querySelector('.btn-delete-card').addEventListener('click', () => {
        if (confirm(`Are you certain you wish to remove "${opt.name}"?`)) {
          options = options.filter(o => o.id !== opt.id);
          saveState();
          renderAll();
        }
      });

      optionsGrid.appendChild(card);
    });
  }

  // --- RENDER LEADER & CHART ---
  function renderLeaderAndChart() {
    let leader = null;
    let maxScore = -1;

    options.forEach(opt => {
      const avg = calculateAverage(opt);
      // Deterministic tie-breaking: higher score, or alphabetical if tied
      if (avg > maxScore) {
        maxScore = avg;
        leader = opt;
      } else if (avg === maxScore && leader) {
        if (opt.name.toLowerCase() < leader.name.toLowerCase()) {
          leader = opt;
        }
      }
    });

    // Update Monolith
    if (leader) {
      leaderName.textContent = leader.name;
      leaderScore.textContent = maxScore;
      leaderDesc.textContent = leader.desc || 'No description recorded for this leading option.';
    } else {
      leaderName.textContent = 'No Options Recorded';
      leaderScore.textContent = '—';
      leaderDesc.textContent = 'Introduce strategic options in the ledger to determine the leading path forward.';
    }

    // Update Chart
    chartBarsContainer.innerHTML = '';
    if (options.length === 0) {
      chartBarsContainer.innerHTML = `<p style="font-size: 0.8rem; font-style: italic; color: #6B6255;">Awaiting comparative data...</p>`;
    } else {
      options.forEach(opt => {
        const avg = calculateAverage(opt);
        const percentage = (avg / 5) * 100;
        const barRow = document.createElement('div');
        barRow.className = 'chart-bar-row';
        barRow.innerHTML = `
          <span class="chart-bar-label" title="${opt.name}">${opt.name}</span>
          <div class="chart-bar-track">
            <div class="chart-bar-fill" style="width: ${percentage}%"></div>
          </div>
          <span class="chart-bar-val">${avg}</span>
        `;
        chartBarsContainer.appendChild(barRow);
      });
    }

    return leader ? leader.id : null;
  }

  // --- RENDER ALL ---
  function renderAll() {
    renderCriteria();
    const leaderId = renderLeaderAndChart();
    renderOptions(leaderId);
  }

  // --- ADD OPTION EVENT ---
  optionForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const name = document.getElementById('opt-name').value.trim();
    const desc = document.getElementById('opt-desc').value.trim();
    
    // Gather scores from form
    const scores = {};
    criteria.forEach(crit => {
      const activeStud = formInitialScores.querySelector(`.studs-container[data-criterion="${crit}"] .stud-btn.active`);
      scores[crit] = activeStud ? parseInt(activeStud.getAttribute('data-val'), 10) : 3;
    });

    const newOption = {
      id: 'opt_' + Date.now(),
      name,
      desc,
      scores
    };

    options.push(newOption);
    saveState();
    
    // Reset form
    optionForm.reset();
    renderAll();
  });

  // --- PURGE LEDGER EVENT ---
  clearBoardBtn.addEventListener('click', () => {
    if (confirm('Are you absolutely certain you wish to purge all options and reset the Atelier ledger? This action is irreversible.')) {
      options = [];
      saveState();
      renderAll();
    }
  });

  // --- INITIALIZE ---
  renderAll();
});