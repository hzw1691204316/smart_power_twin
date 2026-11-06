<template>
  <div class="twin-scene">
    <div ref="host" class="three-host" />
    <div v-if="loading || error" class="scene-loading">
      <span class="loading-orbit" v-if="loading" /><strong>{{ error || '正在加载三维场景' }}</strong
      ><small v-if="loading">{{ progress ? `${progress}%` : 'GLB资源准备中…' }}</small>
    </div>
    <div class="scene-tools">
      <button aria-label="放大场景" @click="zoom(0.8)">＋</button
      ><button aria-label="缩小场景" @click="zoom(1.25)">−</button
      ><button aria-label="恢复场景视角" @click="resetView">⌖</button>
    </div>
    <div class="scene-info">
      {{ loading ? 'MODEL LOADING' : `${meshCount} MESHES` }} <span>/</span> 按需渲染 · 模板演示
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import type { SceneDevice } from '@/types/domain'
import { matchSceneObject } from '@/utils/twinPresentation'

const props = defineProps<{
  modelUrl: string
  devices: SceneDevice[]
  selectedId: string
  dashboard?: boolean
}>()
const emit = defineEmits<{ select: [id: string] }>()
const host = ref<HTMLDivElement>()
const loading = ref(true)
const progress = ref(0)
const error = ref('')
const meshCount = ref(0)
let renderer: THREE.WebGLRenderer | undefined
let scene: THREE.Scene | undefined
let camera: THREE.PerspectiveCamera | undefined
let controls: OrbitControls | undefined
let model: THREE.Object3D | undefined
let highlight: THREE.Box3Helper | undefined
let observer: ResizeObserver | undefined
let disposed = false
let pointerStart = { x: 0, y: 0 }
const deviceMeshes = new Map<string, THREE.Object3D[]>()

function render() {
  if (renderer && scene && camera && !disposed) renderer.render(scene, camera)
}
function resetView() {
  if (!camera || !controls) return
  camera.position.set(
    props.dashboard ? 85 : 95,
    props.dashboard ? 80 : 95,
    props.dashboard ? 102 : 115,
  )
  controls.target.set(0, 2, 0)
  controls.update()
  render()
}
function zoom(factor: number) {
  if (!camera || !controls) return
  const distance = camera.position.distanceTo(controls.target) * factor
  camera.position
    .sub(controls.target)
    .setLength(Math.max(controls.minDistance, Math.min(controls.maxDistance, distance)))
    .add(controls.target)
  controls.update()
  render()
}
function topView() {
  if (!camera || !controls) return
  camera.position.set(0.1, 160, 0.1)
  controls.target.set(0, 0, 0)
  controls.update()
  render()
}
function focusSelected() {
  const objects = deviceMeshes.get(props.selectedId)
  if (!objects?.length || !camera || !controls) return false
  const box = new THREE.Box3()
  objects.forEach((object) => box.union(new THREE.Box3().setFromObject(object)))
  if (box.isEmpty()) return false
  const center = box.getCenter(new THREE.Vector3())
  const distance = Math.min(160, Math.max(25, box.getSize(new THREE.Vector3()).length() * 2.5))
  controls.target.copy(center)
  camera.position
    .copy(center)
    .add(new THREE.Vector3(1, 0.85, 1).normalize().multiplyScalar(distance))
  controls.update()
  render()
  return true
}
defineExpose({ resetView, topView, focusSelected })
function disposeObject(root: THREE.Object3D) {
  const textures = new Set<THREE.Texture>()
  root.traverse((object) => {
    if (!(object instanceof THREE.Mesh || object instanceof THREE.LineSegments)) return
    object.geometry.dispose()
    const materials = Array.isArray(object.material) ? object.material : [object.material]
    materials.forEach((material) => {
      Object.values(material).forEach((value: unknown) => {
        if (value instanceof THREE.Texture) textures.add(value)
      })
      material.dispose()
    })
  })
  textures.forEach((texture) => texture.dispose())
}
function showSelection() {
  if (!scene) return
  if (highlight) {
    scene.remove(highlight)
    highlight.geometry.dispose()
    ;(highlight.material as THREE.Material).dispose()
    highlight = undefined
  }
  const objects = deviceMeshes.get(props.selectedId)
  if (objects?.length) {
    const box = new THREE.Box3()
    objects.forEach((object) => box.union(new THREE.Box3().setFromObject(object)))
    if (!box.isEmpty()) {
      box.expandByScalar(0.4)
      highlight = new THREE.Box3Helper(box, 0x43d9e6)
      scene.add(highlight)
    }
  }
  render()
}
function pointerDown(event: PointerEvent) {
  pointerStart = { x: event.clientX, y: event.clientY }
}
function pointerUp(event: PointerEvent) {
  if (
    !renderer ||
    !camera ||
    !model ||
    Math.hypot(event.clientX - pointerStart.x, event.clientY - pointerStart.y) > 5
  )
    return
  const rect = renderer.domElement.getBoundingClientRect()
  const pointer = new THREE.Vector2(
    ((event.clientX - rect.left) / rect.width) * 2 - 1,
    -((event.clientY - rect.top) / rect.height) * 2 + 1,
  )
  const raycaster = new THREE.Raycaster()
  raycaster.setFromCamera(pointer, camera)
  const hit = raycaster.intersectObject(model, true)[0]
  if (!hit) return
  let object: THREE.Object3D | null = hit.object
  while (object) {
    if (typeof object.userData.deviceId === 'string') {
      emit('select', object.userData.deviceId)
      return
    }
    object = object.parent
  }
}

onMounted(() => {
  try {
    if (!host.value) return
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5))
    renderer.outputColorSpace = THREE.SRGBColorSpace
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.1
    host.value.appendChild(renderer.domElement)
    scene = new THREE.Scene()
    scene.background = props.dashboard ? null : new THREE.Color('#0d2748')
    if (props.dashboard) scene.fog = new THREE.Fog('#173e65', 170, 380)
    camera = new THREE.PerspectiveCamera(42, 1, 0.1, 1000)
    controls = new OrbitControls(camera, renderer.domElement)
    controls.minDistance = 12
    controls.maxDistance = 280
    controls.maxPolarAngle = Math.PI / 2.05
    controls.addEventListener('change', render)
    scene.add(new THREE.HemisphereLight(0xb8e8ff, 0x40554e, 2.8))
    const sun = new THREE.DirectionalLight(0xfff3de, 3.4)
    sun.position.set(40, 90, 30)
    scene.add(sun)
    const rim = new THREE.DirectionalLight(0x72ceff, 1.5)
    rim.position.set(-60, 40, -30)
    scene.add(rim)
    const grid = new THREE.GridHelper(220, 44, 0x337ca6, 0x1d4c73)
    grid.position.y = -0.1
    scene.add(grid)
    observer = new ResizeObserver(() => {
      if (!host.value || !renderer || !camera || disposed) return
      const { width, height } = host.value.getBoundingClientRect()
      if (!width || !height) return
      renderer.setSize(width, height)
      camera.aspect = width / height
      camera.updateProjectionMatrix()
      render()
    })
    observer.observe(host.value)
    renderer.domElement.addEventListener('pointerdown', pointerDown)
    renderer.domElement.addEventListener('pointerup', pointerUp)
    resetView()
    new GLTFLoader().load(
      props.modelUrl,
      (gltf) => {
        if (disposed) {
          disposeObject(gltf.scene)
          return
        }
        model = gltf.scene
        const box = new THREE.Box3().setFromObject(model)
        const size = box.getSize(new THREE.Vector3())
        const scale = 115 / Math.max(size.x, size.y, size.z, 1)
        model.scale.multiplyScalar(scale)
        const scaledBox = new THREE.Box3().setFromObject(model)
        const center = scaledBox.getCenter(new THREE.Vector3())
        model.position.x -= center.x
        model.position.z -= center.z
        model.position.y -= scaledBox.min.y
        // 对象键来自数据库已发布场景；精确/最长完整前缀匹配，也支持GLB分组节点。
        model.traverse((object) => {
          if (object instanceof THREE.Mesh) meshCount.value++
          const device = matchSceneObject(object.name, props.devices)
          if (device) {
            object.userData.deviceId = device.id
            const meshes = deviceMeshes.get(device.id) ?? []
            meshes.push(object)
            deviceMeshes.set(device.id, meshes)
          }
        })
        scene?.add(model)
        loading.value = false
        showSelection()
        render()
      },
      (event) => {
        if (!disposed && event.total)
          progress.value = Math.round((event.loaded / event.total) * 100)
      },
      () => {
        if (!disposed) {
          loading.value = false
          error.value = '模型加载失败，请检查public/models中的文件及浏览器网络请求。'
        }
      },
    )
  } catch (cause) {
    loading.value = false
    error.value = `三维初始化失败：${cause instanceof Error ? cause.message : String(cause)}`
  }
})
watch(() => props.selectedId, showSelection)
onUnmounted(() => {
  disposed = true
  observer?.disconnect()
  controls?.removeEventListener('change', render)
  controls?.dispose()
  if (renderer) {
    renderer.domElement.removeEventListener('pointerdown', pointerDown)
    renderer.domElement.removeEventListener('pointerup', pointerUp)
  }
  if (scene) disposeObject(scene)
  renderer?.dispose()
  renderer?.forceContextLoss()
  renderer?.domElement.remove()
  deviceMeshes.clear()
})
</script>
