import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './AppV2';
import './index.css';
import './landing-overrides.css';
import './landing-flow.css';

createRoot(document.getElementById('root')).render(<StrictMode><App /></StrictMode>);
