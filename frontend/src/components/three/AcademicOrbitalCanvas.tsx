"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

export function AcademicOrbitalCanvas() {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const scene = new THREE.Scene();
    const width = el.clientWidth || 380;
    const height = el.clientHeight || 320;
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
    camera.position.z = 4.6;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    } catch {
      return;
    }
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    el.appendChild(renderer.domElement);

    const coreGeo = new THREE.IcosahedronGeometry(1.35, 1);
    const coreMat = new THREE.MeshBasicMaterial({
      color: 0x7c3aed,
      wireframe: true,
      transparent: true,
      opacity: 0.45,
    });
    const core = new THREE.Mesh(coreGeo, coreMat);
    scene.add(core);

    const ringGeo = new THREE.TorusGeometry(1.9, 0.015, 12, 80);
    const ringMat = new THREE.MeshBasicMaterial({
      color: 0x22d3ee,
      transparent: true,
      opacity: 0.55,
    });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.rotation.x = Math.PI / 3;
    scene.add(ring);

    const ptsGeo = new THREE.BufferGeometry();
    const coords = new Float32Array(120 * 3);
    for (let i = 0; i < 120; i++) {
      const r = 1.65 + (i % 7) * 0.12;
      const theta = i * 0.42;
      const phi = Math.acos(1 - (2 * (i + 0.5)) / 120);
      coords[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      coords[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      coords[i * 3 + 2] = r * Math.cos(phi);
    }
    ptsGeo.setAttribute("position", new THREE.BufferAttribute(coords, 3));
    const ptsMat = new THREE.PointsMaterial({ color: 0x38bdf8, size: 0.05 });
    const points = new THREE.Points(ptsGeo, ptsMat);
    scene.add(points);

    let rafId = 0;
    const animate = () => {
      rafId = requestAnimationFrame(animate);
      core.rotation.y += 0.004;
      core.rotation.x += 0.002;
      ring.rotation.z -= 0.005;
      points.rotation.y -= 0.0025;
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      cancelAnimationFrame(rafId);
      coreGeo.dispose();
      coreMat.dispose();
      ringGeo.dispose();
      ringMat.dispose();
      ptsGeo.dispose();
      ptsMat.dispose();
      renderer.dispose();
      if (renderer.domElement.parentNode === el) {
        el.removeChild(renderer.domElement);
      }
    };
  }, []);

  return (
    <div
      ref={containerRef}
      aria-hidden="true"
      className="h-[300px] w-full max-w-[420px] select-none"
    />
  );
}
