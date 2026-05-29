/* vrmViewer.js — Three.js + @pixiv/three-vrm renderer for Sonya's avatar.
 *
 * Framework-agnostic class: mount(canvas) → load(url) → runs its own RAF loop.
 * Handles idle anims (blink, breathing, micro head-tilt), expression presets
 * (body.expression markers), and amplitude-driven lip-sync (viseme aa).
 *
 * VRM 0.x and 1.0 both supported via @pixiv/three-vrm. Expression names are
 * normalized: we probe the loaded VRM for available expressions and map our
 * canonical markers onto whatever the model exposes.
 *
 * See docs/atrium/ETAP2_RESEARCH.md §3.
 */
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';

// Canonical body.expression markers → candidate VRM expression names.
// VRM 0.x presets: happy/angry/sad/relaxed/surprised + aa/ih/ou/ee/oh/blink.
// VRM 1.0 uses the same preset names. We try each candidate until one exists.
const EXPRESSION_MAP = {
  neutral: ['neutral'],
  smile: ['happy', 'joy', 'fun', 'relaxed'],
  thinking: ['relaxed', 'neutral'],
  tired: ['sad', 'sorrow', 'relaxed'],
  sad: ['sad', 'sorrow'],
  excited: ['happy', 'surprised', 'joy'],
  curious: ['surprised', 'relaxed'],
  tender: ['relaxed', 'happy'],
  annoyed: ['angry'],
};

// Mouth visemes for lip-sync (try VRM1 then VRM0 names).
const VISEME_AA = ['aa', 'a'];

export class VrmViewer {
  constructor() {
    this.renderer = null;
    this.scene = null;
    this.camera = null;
    this.clock = new THREE.Clock();
    this.vrm = null;
    this.raf = null;
    this._expr = 'neutral';
    this._exprWeight = 0; // eased toward 1
    this._activeExprName = null;
    this._mouthTarget = 0; // 0..1 from audio amplitude
    this._mouthCurrent = 0;
    this._blinkTimer = 0;
    this._nextBlinkAt = 2 + Math.random() * 4;
    this._blinkPhase = -1; // -1 = not blinking
    this._headBone = null;
    this._onResize = this._onResize.bind(this);
    this._mounted = false;
    this._disposed = false;
    this.onStatus = null; // optional callback(status:string)
  }

  mount(canvas) {
    this.renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this._resizeToCanvas();

    this.scene = new THREE.Scene();

    this.camera = new THREE.PerspectiveCamera(28, 1, 0.1, 20);
    this.camera.position.set(0, 1.32, 1.55); // head-and-shoulders framing

    // Cold silver-ish lighting matching her palette.
    const key = new THREE.DirectionalLight(0xeaf0f6, 2.2);
    key.position.set(1, 1.4, 1.2);
    this.scene.add(key);
    const fill = new THREE.DirectionalLight(0x8aa3b8, 0.7);
    fill.position.set(-1, 0.6, 0.4);
    this.scene.add(fill);
    this.scene.add(new THREE.AmbientLight(0xb8c0cc, 0.55));

    this._mounted = true;
    window.addEventListener('resize', this._onResize);
    this._loop();
  }

  async load(url) {
    if (!this._mounted) throw new Error('mount() before load()');
    this._setStatus('loading');
    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser));
    try {
      const gltf = await loader.loadAsync(url);
      const vrm = gltf.userData.vrm;
      if (!vrm) throw new Error('no VRM extension in file');

      // Remove previous
      if (this.vrm) {
        this.scene.remove(this.vrm.scene);
        VRMUtils.deepDispose(this.vrm.scene);
        this.vrm = null;
      }

      VRMUtils.removeUnnecessaryVertices(gltf.scene);
      VRMUtils.combineSkeletons(gltf.scene);

      // Face the camera (VRM 0.x models look -Z by default).
      vrm.scene.rotation.y = Math.PI;

      this.scene.add(vrm.scene);
      this.vrm = vrm;
      this._headBone = vrm.humanoid?.getNormalizedBoneNode?.('head') || null;
      this._cacheExpressionNames();
      this._setStatus('ready');
      return vrm;
    } catch (err) {
      this._setStatus('error: ' + (err.message || err));
      throw err;
    }
  }

  // Probe which expression names this VRM actually exposes.
  _cacheExpressionNames() {
    this._available = new Set();
    const em = this.vrm?.expressionManager;
    if (em && em.expressions) {
      for (const e of em.expressions) {
        const n = e.expressionName || e.name;
        if (n) this._available.add(n);
      }
    }
    this._visemeName = VISEME_AA.find((n) => this._available.has(n)) || null;
  }

  _resolveExpr(marker) {
    const candidates = EXPRESSION_MAP[marker] || [marker];
    for (const c of candidates) {
      if (this._available && this._available.has(c)) return c;
    }
    return null;
  }

  // Public: set facial expression by canonical marker (body.expression).
  setExpression(marker) {
    if (marker === this._expr) return;
    this._expr = marker || 'neutral';
  }

  // Public: feed normalized audio amplitude 0..1 for lip-sync.
  setMouthOpen(amount) {
    this._mouthTarget = Math.max(0, Math.min(1, amount || 0));
  }

  _onResize() {
    this._resizeToCanvas();
  }

  _resizeToCanvas() {
    const canvas = this.renderer.domElement;
    const w = canvas.clientWidth || 220;
    const h = canvas.clientHeight || 280;
    this.renderer.setSize(w, h, false);
    if (this.camera) {
      this.camera.aspect = w / h;
      this.camera.updateProjectionMatrix();
    }
  }

  _loop() {
    if (this._disposed) return;
    this.raf = requestAnimationFrame(() => this._loop());
    const dt = Math.min(this.clock.getDelta(), 0.05);
    this._update(dt);
    if (this.vrm) this.vrm.update(dt);
    this.renderer.render(this.scene, this.camera);
  }

  _update(dt) {
    const vrm = this.vrm;
    if (!vrm) return;
    const em = vrm.expressionManager;
    const t = this.clock.elapsedTime;

    // --- breathing (subtle chest/whole-body bob) ---
    if (vrm.scene) {
      vrm.scene.position.y = Math.sin(t * 1.6) * 0.004;
    }

    // --- micro head tilt ---
    if (this._headBone) {
      this._headBone.rotation.z = Math.sin(t * 0.5) * 0.02;
      this._headBone.rotation.x = Math.sin(t * 0.37) * 0.015;
    }

    if (!em) return;

    // --- blink ---
    this._blinkTimer += dt;
    if (this._blinkPhase < 0 && this._blinkTimer >= this._nextBlinkAt) {
      this._blinkPhase = 0;
    }
    if (this._blinkPhase >= 0) {
      this._blinkPhase += dt / 0.12; // ~120ms blink
      const w = this._blinkPhase < 1
        ? Math.sin(Math.min(this._blinkPhase, 1) * Math.PI)
        : 0;
      em.setValue('blink', w);
      if (this._blinkPhase >= 1) {
        this._blinkPhase = -1;
        this._blinkTimer = 0;
        this._nextBlinkAt = 2 + Math.random() * 4;
        em.setValue('blink', 0);
      }
    }

    // --- expression easing ---
    const targetName = this._resolveExpr(this._expr);
    if (targetName !== this._activeExprName) {
      // fade out old
      if (this._activeExprName) em.setValue(this._activeExprName, 0);
      this._activeExprName = targetName;
      this._exprWeight = 0;
    }
    if (this._activeExprName) {
      this._exprWeight += (1 - this._exprWeight) * Math.min(1, dt * 6);
      em.setValue(this._activeExprName, this._exprWeight * 0.85);
    }

    // --- lip-sync (amplitude → viseme) ---
    if (this._visemeName) {
      this._mouthCurrent += (this._mouthTarget - this._mouthCurrent) * Math.min(1, dt * 18);
      em.setValue(this._visemeName, this._mouthCurrent);
    }
  }

  dispose() {
    this._disposed = true;
    if (this.raf) cancelAnimationFrame(this.raf);
    window.removeEventListener('resize', this._onResize);
    if (this.vrm) {
      this.scene.remove(this.vrm.scene);
      VRMUtils.deepDispose(this.vrm.scene);
      this.vrm = null;
    }
    if (this.renderer) {
      this.renderer.dispose();
      this.renderer = null;
    }
  }

  _setStatus(s) {
    if (this.onStatus) this.onStatus(s);
  }
}
