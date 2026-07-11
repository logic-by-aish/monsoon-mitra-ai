// Shared Firebase bootstrap: fetches the NON-SECRET web config from the backend
// (/api/config) so no identifiers are hard-coded in the frontend bundle.
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import {
  getAuth,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut,
} from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";

let cached = null;

export async function getFirebase() {
  if (cached) return cached;
  const resp = await fetch("/api/config");
  const config = await resp.json();
  const app = initializeApp(config);
  const auth = getAuth(app);
  cached = {
    app,
    auth,
    onAuthStateChanged,
    signInWithEmailAndPassword,
    createUserWithEmailAndPassword,
    signOut,
  };
  return cached;
}

// Every dynamic string goes through this before hitting the DOM (XSS defense).
export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
