<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { factorsApi } from '@/api/factors'
import { strategyApi } from '@/api/strategy'

const router = useRouter()

const symbolsInput = ref('600519,300750')
const experimentGoal = ref('')
const experimentNotes = ref('')
const selectedBaseVersion = ref('v1')
const versions = ref<{ version_id: string; name: string }[]>([])
const marketRegime = ref('--')
const effectiveFactorCount = ref(0)
const loadingSnapshot = ref(false)
const creating = ref(false)
const error = ref('')
const draftReady = ref(false)
const experimentCreated = ref(false)

const parsedSymbols = computed(() =>
  symbolsInput.value
    .split(',')
    .map((item) => item.trim().toUpperCase())
    .filter(Boolean)
)

const draftSummary = computed(() => [
  `实验标的：${parsedSymbols.value.join(', ') || '--'}`,
  `实验目标：${experimentGoal.value.trim() || '--'}`,
  `基线版本：${selectedBaseVersion.value || '--'}`,
  `市场状态：${marketRegime.value}`,
  `有效因子数：${effectiveFactorCount.value}`,
])

async function loadContext() {
  loadingSnapshot.value = true
  error.value = ''
  try {
    const [snapshot, versionResp] = await Promise.all([
      factorsApi.daily(new Date().toISOString().slice(0, 10)),
      strategyApi.listVersions(),
    ])
    marketRegime.value = snapshot.market_regime || '--'
    effectiveFactorCount.value = snapshot.effective_factors?.length || 0
    versions.value = versionResp.items
    if (versions.value.length && !versions.value.find((item) => item.version_id === selectedBaseVersion.value)) {
      selectedBaseVersion.value = versions.value[0].version_id
    }
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '加载实验上下文失败。'
  } finally {
    loadingSnapshot.value = false
  }
}

function generateDraft() {
  error.value = ''
  experimentCreated.value = false
  if (!parsedSymbols.value.length || !experimentGoal.value.trim()) {
    error.value = '请先填写实验标的和实验目标。'
    draftReady.value = false
    return
  }
  draftReady.value = true
}

async function createStrategyExperiment() {
  if (!experimentGoal.value.trim()) {
    error.value = '请先填写实验目标。'
    return
  }
  creating.value = true
  error.value = ''
  try {
    await strategyApi.createExperiment({
      base_version_id: selectedBaseVersion.value,
      hypothesis: [
        `实验标的: ${parsedSymbols.value.join(', ') || '--'}`,
        `实验目标: ${experimentGoal.value.trim()}`,
        experimentNotes.value.trim() ? `补充说明: ${experimentNotes.value.trim()}` : '',
      ]
        .filter(Boolean)
        .join('\n'),
    })
    experimentCreated.value = true
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '创建策略实验失败。'
  } finally {
    creating.value = false
  }
}

onMounted(loadContext)
</script>

<template>
  <div class="p-6 max-w-[1200px] mx-auto space-y-5">
    <div class="space-y-2">
      <h1 class="text-xl font-bold text-[var(--text-primary)]">AI实验室</h1>
      <p class="text-sm text-[var(--text-secondary)]">
        这里用于研究假设、形成实验草案并沉淀为策略实验，不会直接触发生产决策，也不会自动进入审批流。
      </p>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-[minmax(0,1.5fr)_360px] gap-5">
      <div class="card p-4 space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="block text-xs text-[var(--text-secondary)] mb-1">实验标的</label>
            <input v-model="symbolsInput" placeholder="600519,300750" />
          </div>
          <div>
            <label class="block text-xs text-[var(--text-secondary)] mb-1">基线策略版本</label>
            <select v-model="selectedBaseVersion">
              <option v-for="item in versions" :key="item.version_id" :value="item.version_id">
                {{ item.version_id }} - {{ item.name }}
              </option>
            </select>
          </div>
        </div>

        <div>
          <label class="block text-xs text-[var(--text-secondary)] mb-1">实验目标</label>
          <textarea v-model="experimentGoal" rows="4" placeholder="例如：验证白酒龙头在震荡市场下的低波动配置价值。" />
        </div>

        <div>
          <label class="block text-xs text-[var(--text-secondary)] mb-1">实验备注</label>
          <textarea v-model="experimentNotes" rows="4" placeholder="记录你希望观察的因子、风险点和对照假设。" />
        </div>

        <div class="flex flex-wrap gap-2">
          <button class="px-4 py-2 rounded bg-[var(--brand-primary)] text-white text-sm" @click="generateDraft">生成实验草案</button>
          <button class="px-4 py-2 rounded border text-sm" @click="loadContext">
            {{ loadingSnapshot ? '刷新中...' : '刷新上下文' }}
          </button>
          <button class="px-4 py-2 rounded border text-sm" @click="router.push('/strategy')">前往策略开发</button>
        </div>

        <p v-if="error" class="text-sm text-[var(--negative)]">{{ error }}</p>
      </div>

      <div class="space-y-5">
        <div class="card p-4 space-y-3">
          <h2 class="font-semibold">实验上下文</h2>
          <div class="text-sm space-y-2">
            <div>市场状态：{{ marketRegime }}</div>
            <div>有效因子数：{{ effectiveFactorCount }}</div>
            <div>基线版本数：{{ versions.length }}</div>
          </div>
        </div>

        <div class="card p-4 space-y-3">
          <h2 class="font-semibold">实验去向</h2>
          <p class="text-sm text-[var(--text-secondary)]">
            AI实验室输出的是研究草案。确认实验方向后，应进入策略开发或因子研究；只有明确要发起正式分析时，才进入决策触发。
          </p>
          <div class="flex flex-col gap-2">
            <button class="px-3 py-2 rounded border text-sm text-left" @click="router.push('/strategy')">进入策略开发</button>
            <button class="px-3 py-2 rounded border text-sm text-left" @click="router.push('/factors')">进入因子研究</button>
            <button class="px-3 py-2 rounded border text-sm text-left" @click="router.push('/analyze')">进入决策触发</button>
          </div>
        </div>
      </div>
    </div>

    <div class="card p-4 space-y-3">
      <div class="flex items-center justify-between">
        <h2 class="font-semibold">实验草案</h2>
        <button
          class="px-3 py-2 rounded bg-[var(--brand-primary)] text-white text-sm disabled:opacity-50"
          :disabled="creating || !draftReady"
          @click="createStrategyExperiment"
        >
          {{ creating ? '创建中...' : '转为策略实验' }}
        </button>
      </div>

      <div v-if="experimentCreated" class="rounded-lg border border-[var(--brand-primary)]/25 bg-[var(--brand-primary-subtle)] px-3 py-2 text-sm text-[var(--brand-primary)]">
        已生成策略实验草案。你可以继续前往策略开发查看实验记录；如需正式产出决策，再进入“决策触发”。
      </div>

      <div v-if="draftReady" class="space-y-2 text-sm">
        <div v-for="line in draftSummary" :key="line">{{ line }}</div>
        <div v-if="experimentNotes.trim()" class="pt-2 border-t border-[var(--border-subtle)] text-[var(--text-secondary)]">
          {{ experimentNotes.trim() }}
        </div>
      </div>
      <p v-else class="text-sm text-[var(--text-tertiary)]">填写实验目标后，点击“生成实验草案”查看摘要。</p>

      <div class="flex flex-wrap gap-2 pt-2">
        <button class="px-3 py-2 rounded border text-sm" @click="router.push('/strategy')">查看策略实验</button>
        <button class="px-3 py-2 rounded border text-sm" @click="router.push('/analyze')">需要正式分析时再去决策触发</button>
      </div>
    </div>
  </div>
</template>
