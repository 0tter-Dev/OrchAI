import { useState } from "react";
import ProjectPicker from "./screens/ProjectPicker.jsx";
import ModuleSelect from "./screens/ModuleSelect.jsx";
import ForgeHome from "./screens/ForgeHome.jsx";
import StudioHome from "./screens/StudioHome.jsx";
import Dashboard from "./screens/Dashboard.jsx";

const MODULE_SCREENS = {
  forge: ForgeHome,
  studio: StudioHome,
};

export default function App() {
  const [screen, setScreen] = useState("picker"); // picker | modules | module-home | dashboard
  const [project, setProject] = useState(null);
  const [module, setModule] = useState(null);

  function handleProjectSelected(selectedProject) {
    setProject(selectedProject);
    setScreen("modules");
  }

  function handleModuleSelected(selectedModule) {
    setModule(selectedModule);
    setScreen("module-home");
  }

  function handleBackToPicker() {
    setProject(null);
    setModule(null);
    setScreen("picker");
  }

  function handleBackToModules() {
    setModule(null);
    setScreen("modules");
  }

  function handleOpenDashboard() {
    setScreen("dashboard");
  }

  if (screen === "modules" && project) {
    return (
      <ModuleSelect
        project={project}
        onModuleSelected={handleModuleSelected}
        onOpenDashboard={handleOpenDashboard}
        onBack={handleBackToPicker}
      />
    );
  }

  if (screen === "module-home" && project && module) {
    const ModuleHome = MODULE_SCREENS[module.module_id];
    if (ModuleHome) {
      return <ModuleHome project={project} module={module} onBack={handleBackToModules} />;
    }
  }

  if (screen === "dashboard" && project) {
    return <Dashboard project={project} onBack={handleBackToModules} />;
  }

  return <ProjectPicker onProjectSelected={handleProjectSelected} />;
}
