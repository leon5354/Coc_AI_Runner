import { createRoot } from "react-dom/client"
import App from "./App"
import { SceneArt } from "./art/SceneArt"
import "./styles.css"

// QA hook: /?art=cellar&mood=night shows one art kit on its own
const qa = new URLSearchParams(location.search)
const kit = qa.get("art")

createRoot(document.getElementById("root")!).render(
  kit ? <SceneArt name={kit} text={qa.get("text") ?? ""} art={kit} mood={qa.get("mood") ?? "night"} /> : <App />)
