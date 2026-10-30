import React, { useMemo } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Html, Grid } from '@react-three/drei';
import * as THREE from 'three';
import { useProjectStore } from '../../store/useProjectStore';

function buildBufferGeometry(
  positions: Float32Array,
  indices: Uint32Array,
  colors: Float32Array
): THREE.BufferGeometry | null {
  if (!positions || positions.length === 0 || !indices || indices.length === 0) {
    return null;
  }
  const geom = new THREE.BufferGeometry();
  // Note: globe3d uses Z-up (North Pole = +Z). In Three.js default Y-up camera,
  // we rotate the scene group by -Math.PI/2 around X so Z-up maps to Three.js Y-up naturally!
  geom.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  if (colors && colors.length === positions.length) {
    geom.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  }
  geom.setIndex(new THREE.BufferAttribute(indices, 1));
  geom.computeVertexNormals();
  return geom;
}

const GlobeMeshScene: React.FC = () => {
  const {
    project,
    meshData,
    viewMode,
    wireframe,
    clippingPlane,
    clippingOffset,
    explodeDistance,
    showMagnetRing,
    showAxes,
    unlitMode,
    magnetAnalysis,
  } = useProjectStore();

  const outerGeometry = useMemo(
    () =>
      buildBufferGeometry(
        meshData.outerPositions,
        meshData.outerIndices,
        meshData.outerColors
      ),
    [meshData.outerPositions, meshData.outerIndices, meshData.outerColors]
  );

  const innerGeometry = useMemo(
    () =>
      buildBufferGeometry(
        meshData.innerPositions,
        meshData.innerIndices,
        meshData.innerColors
      ),
    [meshData.innerPositions, meshData.innerIndices, meshData.innerColors]
  );

  const explodeHalf = viewMode === 'exploded' ? explodeDistance * 0.5 : 0;

  // Clipping planes in world space (where Three.js Y is globe Z, and X is globe X)
  const crossSectionPlanes = useMemo(() => {
    if (!clippingPlane) return [];
    return [new THREE.Plane(new THREE.Vector3(-1, 0, 0), clippingOffset)];
  }, [clippingPlane, clippingOffset]);

  const upperHemispherePlanes = useMemo(() => {
    // Upper hemisphere group is shifted by +explodeHalf in World Y, so its equator is at Y = +explodeHalf.
    // Plane normal (0, 1, 0) keeps Y + constant >= 0  =>  constant = -explodeHalf.
    const planes = [new THREE.Plane(new THREE.Vector3(0, 1, 0), -explodeHalf)];
    if (clippingPlane) planes.push(new THREE.Plane(new THREE.Vector3(-1, 0, 0), clippingOffset));
    return planes;
  }, [clippingPlane, clippingOffset, explodeHalf]);

  const lowerHemispherePlanes = useMemo(() => {
    // Lower hemisphere group is shifted by -explodeHalf in World Y, so its equator is at Y = -explodeHalf.
    // Plane normal (0, -1, 0) keeps -Y + constant >= 0  =>  Y <= constant  =>  constant = -explodeHalf.
    const planes = [new THREE.Plane(new THREE.Vector3(0, -1, 0), -explodeHalf)];
    if (clippingPlane) planes.push(new THREE.Plane(new THREE.Vector3(-1, 0, 0), clippingOffset));
    return planes;
  }, [clippingPlane, clippingOffset, explodeHalf]);

  const showOuter = viewMode !== 'inner';
  const showInner = project.geometry.hollow && viewMode !== 'outer';
  const baseRadius = project.geometry.radius || 40;
  const innerRadius = project.geometry.hollow
    ? baseRadius * (project.geometry.inner_ratio || 0.5)
    : 0;

  // Build accurate equatorial rim/cap geometry from the 360-deg profile (d_min .. d_max)
  const equatorialCapGeometry = useMemo(() => {
    const dMax = magnetAnalysis?.d_max;
    const dMin = magnetAnalysis?.d_min;
    const nSeg = 360;
    const pos = new Float32Array(nSeg * 2 * 3);
    const indices = new Uint32Array(nSeg * 6);

    for (let i = 0; i < nSeg; i++) {
      const rad = (i * Math.PI) / 180.0;
      const cosT = Math.cos(rad);
      const sinT = Math.sin(rad);
      const rIn = project.geometry.hollow
        ? dMin && dMin.length > i
          ? dMin[i]
          : innerRadius
        : 0.0;
      const rOut = dMax && dMax.length > i ? dMax[i] : baseRadius;

      const idxIn = i * 2;
      const idxOut = i * 2 + 1;
      pos[idxIn * 3] = rIn * cosT;
      pos[idxIn * 3 + 1] = rIn * sinT;
      pos[idxIn * 3 + 2] = 0;

      pos[idxOut * 3] = rOut * cosT;
      pos[idxOut * 3 + 1] = rOut * sinT;
      pos[idxOut * 3 + 2] = 0;

      const nextI = (i + 1) % nSeg;
      const nextIn = nextI * 2;
      const nextOut = nextI * 2 + 1;

      const fBase = i * 6;
      indices[fBase] = idxIn;
      indices[fBase + 1] = idxOut;
      indices[fBase + 2] = nextOut;
      indices[fBase + 3] = idxIn;
      indices[fBase + 4] = nextOut;
      indices[fBase + 5] = nextIn;
    }

    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    g.setIndex(new THREE.BufferAttribute(indices, 1));
    g.computeVertexNormals();
    return g;
  }, [magnetAnalysis?.d_min, magnetAnalysis?.d_max, project.geometry.hollow, innerRadius, baseRadius]);

  const renderMaterial = (planes: THREE.Plane[], isWire: boolean = false) => {
    if (isWire) {
      return (
        <meshBasicMaterial
          color="#38bdf8"
          wireframe
          transparent
          opacity={0.28}
          clippingPlanes={planes}
        />
      );
    }
    if (unlitMode) {
      return (
        <meshBasicMaterial
          vertexColors
          side={THREE.DoubleSide}
          clippingPlanes={planes}
        />
      );
    }
    return (
      <meshStandardMaterial
        vertexColors
        roughness={0.55}
        metalness={0.08}
        side={THREE.DoubleSide}
        clippingPlanes={planes}
        clipShadows
      />
    );
  };

  const renderHalf = (
    planes: THREE.Plane[],
    yOffset: number,
    keyPrefix: string,
    showEquatorialCap: boolean = false
  ) => (
    <group key={keyPrefix} position={[0, yOffset, 0]}>
      {/* Rotate -90 deg around X so Globe Z-axis (North Pole) aligns with Three.js +Y */}
      <group rotation={[-Math.PI / 2, 0, 0]}>
        {showOuter && outerGeometry && (
          <mesh geometry={outerGeometry}>
            {renderMaterial(planes, false)}
          </mesh>
        )}
        {showOuter && wireframe && outerGeometry && (
          <mesh geometry={outerGeometry}>
            {renderMaterial(planes, true)}
          </mesh>
        )}
        {showInner && innerGeometry && (
          <mesh geometry={innerGeometry}>
            {renderMaterial(planes, false)}
          </mesh>
        )}
        {showInner && wireframe && innerGeometry && (
          <mesh geometry={innerGeometry}>
            {renderMaterial(planes, true)}
          </mesh>
        )}
        {showEquatorialCap && showOuter && (
          <mesh geometry={equatorialCapGeometry}>
            <meshStandardMaterial
              color="#64748b"
              roughness={0.65}
              metalness={0.1}
              side={THREE.DoubleSide}
              clippingPlanes={crossSectionPlanes}
            />
          </mesh>
        )}
      </group>
    </group>
  );

  const rVoid =
    (project.magnets.diameter || 5.0) * 0.5 +
    (project.magnets.horizontal_tolerance ?? 0.15);
  const hVoid =
    (project.magnets.height || 2.0) + (project.magnets.vertical_tolerance ?? 0.1);
  const vOffset = project.magnets.vertical_offset ?? 0.2;
  const minThick = project.magnets.min_thickness ?? 1.5;
  const rBoss = rVoid + minThick;
  const hBoss = vOffset + hVoid + minThick;

  return (
    <group>
      {viewMode === 'exploded' ? (
        <>
          {renderHalf(upperHemispherePlanes, explodeHalf, 'exploded-top', true)}
          {renderHalf(lowerHemispherePlanes, -explodeHalf, 'exploded-bot', true)}
        </>
      ) : viewMode === 'upper' ? (
        renderHalf(upperHemispherePlanes, 0, 'upper-only', true)
      ) : viewMode === 'lower' ? (
        renderHalf(lowerHemispherePlanes, 0, 'lower-only', true)
      ) : (
        renderHalf(crossSectionPlanes, 0, 'whole-globe', false)
      )}

      {/* Equatorial Cut & Magnet Ring Visualization */}
      {showMagnetRing && project.magnets.enabled && (
        <group rotation={[-Math.PI / 2, 0, 0]}>
          {/* Translucent equatorial ring between inner and outer radius */}
          {viewMode === 'whole' && (
            <mesh geometry={equatorialCapGeometry}>
              <meshBasicMaterial
                color="#38bdf8"
                transparent
                opacity={0.14}
                side={THREE.DoubleSide}
                clippingPlanes={crossSectionPlanes}
              />
            </mesh>
          )}

          {/* Two Separate Magnet Voids (Top & Bottom with 2*vertical_offset gap) & Enclosing Bosses */}
          {(magnetAnalysis?.magnets || []).map((m) => {
            const color = !m.valid ? '#ef4444' : m.needs_boss ? '#f59e0b' : '#10b981';
            const topVoidZ = explodeHalf + vOffset + hVoid * 0.5;
            const botVoidZ = -explodeHalf - (vOffset + hVoid * 0.5);
            const topBossZ = explodeHalf + hBoss * 0.5;
            const botBossZ = -explodeHalf - hBoss * 0.5;
            const showTopMag = viewMode !== 'lower';
            const showBotMag = viewMode !== 'upper';

            return (
              <group key={m.index} position={[m.center[0], m.center[1], 0]}>
                {/* Upper Hemisphere Magnet Void */}
                {showTopMag && (
                  <mesh position={[0, 0, topVoidZ]} rotation={[Math.PI / 2, 0, 0]}>
                    <cylinderGeometry args={[rVoid, rVoid, hVoid, 28]} />
                    <meshStandardMaterial
                      color={color}
                      emissive={color}
                      emissiveIntensity={0.35}
                      roughness={0.3}
                      metalness={0.2}
                      clippingPlanes={crossSectionPlanes}
                    />
                  </mesh>
                )}

                {/* Lower Hemisphere Magnet Void */}
                {showBotMag && (
                  <mesh position={[0, 0, botVoidZ]} rotation={[Math.PI / 2, 0, 0]}>
                    <cylinderGeometry args={[rVoid, rVoid, hVoid, 28]} />
                    <meshStandardMaterial
                      color={color}
                      emissive={color}
                      emissiveIntensity={0.35}
                      roughness={0.3}
                      metalness={0.2}
                      clippingPlanes={crossSectionPlanes}
                    />
                  </mesh>
                )}

                {/* Enclosing Bosses (separate upper & lower hemisphere bosses) */}
                {m.needs_boss && showTopMag && (
                  <mesh position={[0, 0, topBossZ]} rotation={[Math.PI / 2, 0, 0]}>
                    <cylinderGeometry args={[rBoss, rBoss, hBoss, 28]} />
                    <meshBasicMaterial
                      color="#f59e0b"
                      wireframe
                      transparent
                      opacity={0.55}
                      clippingPlanes={crossSectionPlanes}
                    />
                  </mesh>
                )}
                {m.needs_boss && showBotMag && (
                  <mesh position={[0, 0, botBossZ]} rotation={[Math.PI / 2, 0, 0]}>
                    <cylinderGeometry args={[rBoss, rBoss, hBoss, 28]} />
                    <meshBasicMaterial
                      color="#f59e0b"
                      wireframe
                      transparent
                      opacity={0.55}
                      clippingPlanes={crossSectionPlanes}
                    />
                  </mesh>
                )}

                <Html
                  distanceFactor={140}
                  position={[0, 0, showTopMag ? topVoidZ + hVoid * 0.9 : botVoidZ - hVoid * 0.9]}
                >
                  <div className="px-1.5 py-0.5 rounded bg-slate-900/90 border border-slate-700 text-[10px] font-mono text-slate-200 whitespace-nowrap shadow">
                    #{m.index + 1} ({m.angle_deg}°)
                  </div>
                </Html>
              </group>
            );
          })}
        </group>
      )}

      {/* North / South Pole Labels & Coordinate Axes */}
      {showAxes && (
        <group>
          <Html
            position={[
              0,
              baseRadius * 1.16 + (viewMode === 'exploded' ? explodeDistance * 0.5 : 0),
              0,
            ]}
            center
          >
            <div className="px-2 py-0.5 rounded-full bg-red-500/20 border border-red-400/50 text-red-300 text-xs font-bold tracking-wider shadow">
              N
            </div>
          </Html>
          <Html
            position={[
              0,
              -baseRadius * 1.16 - (viewMode === 'exploded' ? explodeDistance * 0.5 : 0),
              0,
            ]}
            center
          >
            <div className="px-2 py-0.5 rounded-full bg-sky-500/20 border border-sky-400/50 text-sky-300 text-xs font-bold tracking-wider shadow">
              S
            </div>
          </Html>
          <Grid
            position={[0, -baseRadius * 1.35, 0]}
            args={[200, 200]}
            cellSize={10}
            cellThickness={0.5}
            cellColor="#1e293b"
            sectionSize={50}
            sectionThickness={1}
            sectionColor="#334155"
            fadeDistance={220}
            infiniteGrid
          />
        </group>
      )}
    </group>
  );
};

export const GlobeCanvas: React.FC = () => {
  const { autoRotate, project } = useProjectStore();
  const camDist = Math.max(85, (project.geometry.radius || 40) * 2.55);

  return (
    <div className="w-full h-full relative bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950">
      <Canvas
        gl={{ localClippingEnabled: true, antialias: true, preserveDrawingBuffer: true }}
        camera={{ position: [camDist * 0.75, camDist * 0.45, camDist * 0.75], fov: 42, near: 0.5, far: 2000 }}
      >
        <ambientLight intensity={0.65} />
        <directionalLight position={[120, 160, 100]} intensity={1.15} />
        <directionalLight position={[-120, -90, -100]} intensity={0.45} />
        <GlobeMeshScene />
        <OrbitControls
          makeDefault
          autoRotate={autoRotate}
          autoRotateSpeed={1.2}
          enableDamping
          dampingFactor={0.08}
        />
      </Canvas>
    </div>
  );
};
