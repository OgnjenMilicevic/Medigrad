let currentDatasetSession = null;

function createDatasetSession({ headers = [], filename = null } = {}) {
  const datasetId = `ds_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

  currentDatasetSession = {
    id: datasetId,
    filename,
    headers: [...headers],
    dialogStateByTask: {},
    actionLog: [], // not used yet, but keeps the architecture ready
  };

  return currentDatasetSession;
}

function clearDatasetSession() {
  currentDatasetSession = null;
}

function getCurrentDatasetSession() {
  return currentDatasetSession;
}

function getCurrentDatasetId() {
  return currentDatasetSession?.id ?? null;
}

function getDialogState(taskType) {
  if (!currentDatasetSession) return null;
  return currentDatasetSession.dialogStateByTask[taskType] ?? null;
}

function setDialogState(taskType, params) {
  if (!currentDatasetSession) return;

  currentDatasetSession.dialogStateByTask[taskType] = {
    ...params,
  };
}

function recordAction(action) {
  if (!currentDatasetSession) return;

  currentDatasetSession.actionLog.push({
    ...action,
    timestamp: new Date().toISOString(),
    datasetId: currentDatasetSession.id,
  });
}

export {
  createDatasetSession,
  clearDatasetSession,
  getCurrentDatasetSession,
  getCurrentDatasetId,
  getDialogState,
  setDialogState,
  recordAction,
};