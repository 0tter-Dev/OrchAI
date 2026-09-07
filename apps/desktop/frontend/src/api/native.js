// Bridge to apps/desktop/shell/native_bridge.py, exposed by pywebview as
// window.pywebview.api once the native window has finished wiring it up.

export function onPywebviewReady(callback) {
  if (window.pywebview) {
    callback();
    return;
  }
  window.addEventListener("pywebviewready", callback, { once: true });
}

export const native = {
  isAvailable: () => Boolean(window.pywebview),
  pickFolder: () => window.pywebview.api.pick_folder(),
  listRecentProjects: () => window.pywebview.api.list_recent_projects(),
  addRecentProject: (path, name) => window.pywebview.api.add_recent_project(path, name),
};
