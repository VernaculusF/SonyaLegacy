/* Atrium frontend entry. Mounts <App/> into #root. */
import { render } from 'solid-js/web';
import App from './App.jsx';

const root = document.getElementById('root');
render(() => <App />, root);
