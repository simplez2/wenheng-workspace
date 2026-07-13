import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { APP_NAME } from './branding';

document.title = APP_NAME;

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
