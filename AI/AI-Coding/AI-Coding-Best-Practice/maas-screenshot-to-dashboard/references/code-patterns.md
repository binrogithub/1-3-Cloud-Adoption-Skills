# Code Patterns Reference

## Ant Design Dark Theme Setup

### App.tsx

```tsx
import { ConfigProvider, theme } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import Dashboard from './pages/Dashboard';

const App = () => (
  <ConfigProvider
    locale={zhCN}
    theme={{
      algorithm: theme.darkAlgorithm,
      token: {
        colorPrimary: '#1890ff',
        borderRadius: 4,
        colorBgContainer: '#0A1945',   // Card background
        colorBgElevated: '#1F2241',     // Elevated surface
        colorBgLayout: '#050C38',       // Page background (navy)
      },
    }}
  >
    <Dashboard />
  </ConfigProvider>
);

export default App;
```

### index.css (Navy Surface Overrides)

```css
body {
  margin: 0;
  padding: 0;
  background: #050C38;  /* Deep navy — NOT default dark #000 */
}

#root { min-height: 100vh; }

/* Ant Design table overrides for compact dark style */
.ant-table { background: transparent !important; }
.ant-table-thead > tr > th {
  background: rgba(255, 255, 255, 0.04) !important;
  color: #ffffffa6 !important;
  font-size: 12px !important;
  padding: 6px 8px !important;
}
.ant-table-tbody > tr > td {
  border-bottom: 1px solid rgba(255, 255, 255, 0.06) !important;
  color: #ffffffd9 !important;
  font-size: 12px !important;
  padding: 6px 8px !important;
}

/* Card overrides */
.ant-card {
  color: #ffffffd9;
  background: rgba(255, 255, 255, 0.04) !important;
  border: 1px solid rgba(255, 255, 255, 0.08) !important;
  border-radius: 6px !important;
}
```

## Text Opacity Tiers

| Tier | Hex | Opacity | Use |
|---|---|---|---|
| Primary | `#FFFFFF` | 100% | Titles, values, headings |
| Secondary | `#ffffffd9` | 85% | Body text, labels |
| Muted | `#ffffffa6` | 65% | Captions, subtitles, secondary labels |
| Faint | `#ffffff4d` | 30% | Tertiary info, "较上月" type text |

## BilingualTitle Component

```tsx
interface BilingualTitleProps {
  title: string;    // Chinese primary
  subtitle: string; // English secondary
  style?: React.CSSProperties;
}

const BilingualTitle = ({ title, subtitle, style }: BilingualTitleProps) => (
  <div style={{
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    ...style
  }}>
    <span style={{ color: '#fff', fontSize: 13, fontWeight: 500 }}>{title}</span>
    <span style={{ color: '#ffffffa6', fontSize: 11 }}>{subtitle}</span>
  </div>
);
```

## KPI Card with SVG Progress Ring

```tsx
// Percent variant — circular progress ring
<div style={{ position: 'relative', width: 56, height: 56, margin: '0 auto' }}>
  <svg viewBox="0 0 36 36" style={{ width: '100%', height: '100%', transform: 'rotate(-90deg)' }}>
    {/* Background ring */}
    <circle cx="18" cy="18" r="15.5" fill="none"
      stroke="rgba(255,255,255,0.08)" strokeWidth="3" />
    {/* Progress ring */}
    <circle cx="18" cy="18" r="15.5" fill="none"
      stroke={color} strokeWidth="3"
      strokeDasharray={`${percent * 0.974} ${97.4 - percent * 0.974}`}
      strokeLinecap="round" />
  </svg>
  {/* Center text */}
  <div style={{
    position: 'absolute', inset: 0,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    color: '#fff', fontSize: 13, fontWeight: 600,
  }}>
    {percent}%
  </div>
</div>
```

**Ring math**: circumference = 2π × 15.5 ≈ 97.4. `strokeDasharray = [percent × 0.974, 97.4 - percent × 0.974]`

## ECharts Dark Theme Config

Common config for all charts:

```tsx
const darkChartConfig = {
  backgroundColor: 'transparent',
  tooltip: {
    backgroundColor: '#1a1a2e',
    borderColor: 'rgba(255,255,255,0.06)',
    textStyle: { color: '#fff', fontSize: 12 },
  },
  grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
  xAxis: {
    axisLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
    axisLabel: { color: '#ffffff73', fontSize: 11 },
  },
  yAxis: {
    axisLine: { show: false },
    splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
    axisLabel: { color: '#ffffff73', fontSize: 11 },
  },
};
```

## ECharts Map (Choropleth)

```tsx
import { useEffect, useState } from 'react';
import * as echarts from 'echarts';
import ReactECharts from 'echarts-for-react';

const MapComponent = () => {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    fetch('/brazil.json')
      .then(res => res.json())
      .then(data => {
        echarts.registerMap('brazil', data);
        setReady(true);
      });
  }, []);

  if (!ready) return <div>Loading map...</div>;

  const option = {
    backgroundColor: 'transparent',
    series: [{
      type: 'map',
      map: 'brazil',
      roam: false,
      label: { show: false },
      emphasis: {
        label: { show: true, color: '#fff' },
        itemStyle: { areaColor: '#3498db' },
      },
      itemStyle: {
        borderColor: 'rgba(255,255,255,0.12)',
        borderWidth: 0.8,
      },
      data: [
        { name: 'Reg 1', value: 1, itemStyle: { color: '#1b4f72' } },
        // ...
      ],
    }],
  };

  return <ReactECharts option={option} style={{ height: '100%', minHeight: 220 }} />;
};
```

**GeoJSON sources**:
- Natural Earth (recommended): `https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_1_states_provinces.geojson` — filter by `adm0_a3` country code
- Aliyun DataV: `https://geo.datav.aliyun.com/areas_v3/bound/<adcode>_full.json` — China provinces only

## Dashboard 3-Column Layout

```tsx
<div style={{
  display: 'grid',
  gridTemplateColumns: '25% 45% 30%',
  gap: 12,
  minHeight: 500,
}}>
  {/* Left: Map + Tables */}
  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
    <MapCard />
    <Top10Table1 />
    <Top10Table2 />
  </div>

  {/* Center: Main chart */}
  <div style={{ ...cardStyle }}>
    <MainChart />
  </div>

  {/* Right: Stacked charts */}
  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
    <Chart1 />
    <Chart2 />
    <Chart3 />
  </div>
</div>
```

## Card Container Pattern

Every chart/table lives inside a card:

```tsx
const cardStyle = {
  background: 'rgba(255,255,255,0.04)',
  border: '1px solid rgba(255,255,255,0.08)',
  borderRadius: 6,
};

// With BilingualTitle header
<div style={{ ...cardStyle, overflow: 'hidden' }}>
  <div style={{
    borderBottom: '1px solid rgba(255,255,255,0.06)',
    padding: '8px 12px',
  }}>
    <BilingualTitle title="中文标题" subtitle="English Title" />
  </div>
  <ReactECharts option={option} style={{ height: 180 }} />
</div>
```
