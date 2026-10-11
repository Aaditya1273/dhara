import { createRoot } from 'react-dom/client';
import { App } from './App';
import './styles/landing.css';

const root = document.getElementById('landing-root');
if (root) createRoot(root).render(<App />);
