/**
 * 跨端复用 UI 组件 (@ielts/ui)
 *
 * system-architecture §4.3：跨 user-web / admin-web 复用组件（如音频播放器）。
 *
 * 阶段 1 骨架：仅导出占位组件与 props 类型，验证 workspace 引用链路。
 * Phase 6 迁移为 .vue SFC（AudioPlayer / RecordingWaveform 等）并补充 vue-tsc。
 */

import { defineComponent, h } from 'vue';

/** 音频播放器 props（Phase 6 实现 AudioPlayer.vue 时对齐）。 */
export interface AudioPlayerProps {
  src: string;
  durationSeconds?: number;
}

/**
 * 占位音频播放器组件。
 *
 * Phase 6 替换为完整实现（<audio> 控件 + 波形 + 时长展示），
 * 对齐 ADR-016 duration 口径（后端计算，前端只展示）。
 */
export const BaseAudioPlayer = defineComponent({
  name: 'BaseAudioPlayer',
  props: {
    src: { type: String, required: true },
    durationSeconds: { type: Number, default: 0 },
  },
  setup(props) {
    return () =>
      h('audio', { controls: true, src: props.src });
  },
});
