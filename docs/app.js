const statusMessage = document.querySelector("#status-message");
const randomizeButton = document.querySelector("#randomize-button");
const setSelect = document.querySelector("#set-select");
const modeSelect = document.querySelector("#mode-select");
const playersSection = document.querySelector("#players");
const mePacks = document.querySelector("#me-packs");
const youPacks = document.querySelector("#you-packs");
const meDescription = document.querySelector("#me-description");
const youDescription = document.querySelector("#you-description");

const PAIRING_MODES = {
  AVOID_MONOCOLOR: "avoid-monocolor",
  MONOCOLOR: "monocolor",
  FULLY_RANDOM: "fully-random",
};

const SET_SELECTIONS = {
  ALL_SETS: "all-sets",
  SET_VS_SET: "set-vs-set",
};

const state = {
  sets: {},
  setCode: "",
  pairingMode: PAIRING_MODES.AVOID_MONOCOLOR,
  packs: [],
  setName: "",
};

function shuffle(items) {
  const copy = [...items];
  for (let index = copy.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(Math.random() * (index + 1));
    [copy[index], copy[swapIndex]] = [copy[swapIndex], copy[index]];
  }
  return copy;
}

function individualSets() {
  return Object.values(state.sets).sort((left, right) => left.setCode.localeCompare(right.setCode));
}

function allPacks() {
  return individualSets().flatMap((setPayload) => setPayload.packs);
}

function areCompatiblePacks(firstPack, secondPack, pairingMode) {
  if (firstPack.id === secondPack.id) {
    return false;
  }

  if (pairingMode === PAIRING_MODES.FULLY_RANDOM) {
    return true;
  }

  if (pairingMode === PAIRING_MODES.MONOCOLOR) {
    if (firstPack.isMulticolor || secondPack.isMulticolor) {
      return false;
    }

    if (firstPack.colorCodes.length !== 1 || secondPack.colorCodes.length !== 1) {
      return false;
    }

    return firstPack.colorCodes[0] === secondPack.colorCodes[0];
  }

  if (firstPack.isMulticolor || secondPack.isMulticolor) {
    return true;
  }

  if (firstPack.colorCodes.length !== 1 || secondPack.colorCodes.length !== 1) {
    return true;
  }

  return firstPack.colorCodes[0] !== secondPack.colorCodes[0];
}

function pickPair(packs, usedIds, pairingMode) {
  const availablePacks = shuffle(packs.filter((pack) => !usedIds.has(pack.id)));

  for (const firstPack of availablePacks) {
    const options = availablePacks.filter(
      (candidate) =>
        candidate.id !== firstPack.id && areCompatiblePacks(firstPack, candidate, pairingMode),
    );

    if (options.length > 0) {
      const secondPack = options[Math.floor(Math.random() * options.length)];
      return [firstPack, secondPack];
    }
  }

  throw new Error("Unable to find a valid pack pair.");
}

function drawStandardMatchup(packs) {
  for (let attempt = 0; attempt < 200; attempt += 1) {
    try {
      const usedIds = new Set();
      const me = pickPair(packs, usedIds, state.pairingMode);
      me.forEach((pack) => usedIds.add(pack.id));
      const you = pickPair(packs, usedIds, state.pairingMode);
      return { me, you };
    } catch (error) {
      continue;
    }
  }

  throw new Error("Unable to randomize four unique packs.");
}

function drawSetVsSetMatchup() {
  const sets = individualSets();
  if (sets.length < 2) {
    throw new Error("Set Vs Set requires at least two sets.");
  }

  for (let attempt = 0; attempt < 200; attempt += 1) {
    try {
      const [meSet, youSet] = shuffle(sets).slice(0, 2);
      return {
        me: pickPair(meSet.packs, new Set(), state.pairingMode),
        you: pickPair(youSet.packs, new Set(), state.pairingMode),
        meSet,
        youSet,
      };
    } catch (error) {
      continue;
    }
  }

  throw new Error("Unable to randomize a valid Set Vs Set matchup.");
}

function drawMatchup() {
  if (state.setCode === SET_SELECTIONS.SET_VS_SET) {
    return drawSetVsSetMatchup();
  }

  return drawStandardMatchup(state.packs);
}

function packCardMarkup(pack) {
  return `
    <article class="pack-card">
      <img src="${pack.imageUrl}" alt="${pack.name} Jumpstart front card">
      <div class="pack-card-body">
        <h3>${pack.name}</h3>
        <div class="pack-meta">
          <span class="color-badge">${pack.colorLabel}</span>
          <span class="set-badge">${pack.setCode.toUpperCase()}</span>
          <span class="pack-number">#${pack.collectorNumber}</span>
        </div>
      </div>
    </article>
  `;
}

function renderSelection(selection) {
  mePacks.innerHTML = selection.me.map(packCardMarkup).join("");
  youPacks.innerHTML = selection.you.map(packCardMarkup).join("");
  playersSection.hidden = false;
  if (selection.meSet && selection.youSet) {
    meDescription.textContent = `${selection.meSet.setCode.toUpperCase()} • ${selection.meSet.setName}`;
    youDescription.textContent = `${selection.youSet.setCode.toUpperCase()} • ${selection.youSet.setName}`;
    statusMessage.textContent = `${selection.meSet.setCode.toUpperCase()} vs ${selection.youSet.setCode.toUpperCase()} • packs loaded`;
    return;
  }

  meDescription.textContent = `Two packs from ${state.setName}.`;
  youDescription.textContent = `Two more packs from ${state.setName}.`;
  statusMessage.textContent = `${state.setName} • ${state.packs.length} packs loaded`;
}

function hideSelection() {
  playersSection.hidden = true;
  mePacks.innerHTML = "";
  youPacks.innerHTML = "";
  meDescription.textContent = "Two packs from the selected set using the chosen pairing mode.";
  youDescription.textContent = "Built from the same selected Jumpstart front-card pool.";
}

function loadPacks() {
  if (state.setCode === SET_SELECTIONS.ALL_SETS) {
    state.packs = allPacks();
    state.setName = "All Sets";
    return;
  }

  if (state.setCode === SET_SELECTIONS.SET_VS_SET) {
    state.packs = allPacks();
    state.setName = "Set Vs Set";
    return;
  }

  const payload = state.sets[state.setCode];
  if (!payload || !Array.isArray(payload.packs) || payload.packs.length === 0) {
    throw new Error("Pack data is missing.");
  }

  state.packs = payload.packs;
  state.setName = payload.setName;
}

function updateReadyStatus() {
  if (state.setCode === SET_SELECTIONS.SET_VS_SET) {
    statusMessage.textContent = `Set Vs Set • ${individualSets().length} sets ready`;
    return;
  }

  statusMessage.textContent = `${state.setName} • ${state.packs.length} packs ready`;
}

function initializeSetOptions() {
  const sets = individualSets();
  if (sets.length === 0) {
    throw new Error("No Jumpstart sets are available.");
  }

  const specialOptions = [
    `<option value="${SET_SELECTIONS.ALL_SETS}">All Sets • Combined pool</option>`,
    `<option value="${SET_SELECTIONS.SET_VS_SET}">Set Vs Set • Different set per player</option>`,
  ];

  const setOptions = sets.map(
    (payload) =>
      `<option value="${payload.setCode}">${payload.setCode.toUpperCase()} • ${payload.setName}</option>`,
  );

  setSelect.innerHTML = [...specialOptions, ...setOptions].join("");

  state.setCode = state.sets.fmsc ? "fmsc" : sets[0].setCode;
  setSelect.value = state.setCode;
}

function switchSet(setCode) {
  state.setCode = setCode;
  loadPacks();
  hideSelection();
  updateReadyStatus();
}

function initialize() {
  try {
    state.sets = Object.fromEntries(
      Object.entries(window.JUMPSTART_SETS || {}).map(([setCode, payload]) => [
        setCode,
        {
          ...payload,
          packs: payload.packs.map((pack) => ({
            ...pack,
            setCode: payload.setCode,
            setName: payload.setName,
          })),
        },
      ]),
    );
    initializeSetOptions();
    state.pairingMode = modeSelect.value;
    switchSet(state.setCode);
    setSelect.disabled = false;
    modeSelect.disabled = false;
    randomizeButton.disabled = false;
  } catch (error) {
    statusMessage.textContent = error.message;
    setSelect.disabled = true;
    modeSelect.disabled = true;
    randomizeButton.disabled = true;
  }
}

setSelect.addEventListener("change", (event) => {
  try {
    switchSet(event.target.value);
  } catch (error) {
    statusMessage.textContent = error.message;
  }
});

modeSelect.addEventListener("change", (event) => {
  state.pairingMode = event.target.value;
  hideSelection();
  updateReadyStatus();
});

randomizeButton.addEventListener("click", () => {
  try {
    renderSelection(drawMatchup());
  } catch (error) {
    statusMessage.textContent = error.message;
  }
});

setSelect.disabled = true;
modeSelect.disabled = true;
randomizeButton.disabled = true;
initialize();
