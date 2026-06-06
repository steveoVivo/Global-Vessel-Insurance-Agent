import { useEffect, useRef } from 'react';
import * as d3 from 'd3';

import getSelectionContext from './selectionContext';
import getTrendContext, { MonthlyPoint, PredictedYearlyPoint } from './trendContext';

const MARGIN = { top: 12, right: 16, bottom: 28, left: 52 };
const CLIP_ID = 'trend-clip';
const X_MAX = 2028.75; // show through end of predictions (2028)
const QUARTERLY_THRESHOLD = 4; // switch to quarterly ticks when < 4 years visible

interface QuarterlyPoint {
  year: number;
  quarter: number;
  x: number;        // year + (quarter-1)/4  →  2011.0, 2011.25, …
  label: string;
  accident_rate: number;
  accident_count: number;
  exposure: number;
  has_fleet_data: boolean;
}

function toQuarterly(monthly: MonthlyPoint[]): QuarterlyPoint[] {
  const map = new Map<string, QuarterlyPoint>();
  for (const m of monthly) {
    const q = Math.ceil(m.month / 3);
    const key = `${m.year}-Q${q}`;
    const existing = map.get(key);
    if (existing) {
      existing.accident_count += m.accident_count;
      existing.exposure      += m.exposure;
      if (m.has_fleet_data) existing.has_fleet_data = true;
    } else {
      map.set(key, {
        year: m.year, quarter: q,
        x: m.year + (q - 1) / 4,
        label: `${m.year} Q${q}`,
        accident_count: m.accident_count,
        exposure: m.exposure,
        has_fleet_data: m.has_fleet_data,
        accident_rate: 0,
      });
    }
  }
  for (const pt of map.values()) {
    pt.accident_rate = pt.exposure > 0 ? pt.accident_count / pt.exposure : 0;
  }
  return Array.from(map.values())
    .filter(pt => pt.has_fleet_data || pt.accident_count > 0)
    .sort((a, b) => a.x - b.x);
}

/** Generate all quarterly x values between xMin and X_MAX */
function allQuarterlyTicks(xMin: number): number[] {
  const ticks: number[] = [];
  for (let yr = Math.ceil(xMin); yr <= 2028; yr++) {
    for (let q = 0; q < 4; q++) ticks.push(yr + q / 4);
  }
  return ticks;
}

function quarterLabel(x: number): string {
  const yr = Math.floor(x);
  const q  = Math.round((x - yr) * 4) + 1;
  return `${yr} Q${q}`;
}

function TrendComponent() {
  const { currentCountry } = getSelectionContext();
  const { trendByFlag, loading } = getTrendContext();
  const svgRef        = useRef<SVGSVGElement>(null);
  const containerRef  = useRef<HTMLDivElement>(null);
  const resetBtnRef   = useRef<HTMLButtonElement>(null);
  const zoomRef       = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);

  useEffect(() => {
    const svg       = svgRef.current;
    const container = containerRef.current;
    const resetBtn  = resetBtnRef.current;
    if (!svg || !container) return;

    svg.removeAttribute('width');
    svg.removeAttribute('height');
    d3.select(svg).selectAll('*').remove();
    if (resetBtn) resetBtn.style.display = 'none';
    zoomRef.current  = null;

    if (!currentCountry) return;
    const trend = trendByFlag.get(currentCountry);
    if (!trend) return;

    const points = toQuarterly(trend.monthly);
    if (points.length === 0) return;
    const predicted = trend.predicted_yearly ?? [];

    const width  = svg.clientWidth  || container.clientWidth  || 300;
    const height = svg.clientHeight || 140;
    const innerW = Math.max(width  - MARGIN.left - MARGIN.right,  10);
    const innerH = Math.max(height - MARGIN.top  - MARGIN.bottom, 10);

    svg.setAttribute('width',  String(width));
    svg.setAttribute('height', String(height));

    const svgSel = d3.select(svg);

    svgSel.append('defs').append('clipPath').attr('id', CLIP_ID)
      .append('rect').attr('width', innerW).attr('height', innerH + 4).attr('y', -4);

    const g = svgSel.append('g').attr('transform', `translate(${MARGIN.left},${MARGIN.top})`);

    const xMin = d3.min(points, d => d.x)!;
    const xScale = d3.scaleLinear()
      .domain([xMin, X_MAX])
      .range([0, innerW]);

    const maxHistorical = d3.max(points, d => d.accident_rate) ?? 0.01;
    const maxPredicted  = predicted.length > 0 ? d3.max(predicted, d => d.accident_rate) ?? 0 : 0;
    const maxRate = Math.max(maxHistorical, maxPredicted);
    const yScale = d3.scaleLinear()
      .domain([0, maxRate * 1.15])
      .range([innerH, 0]);

    // Gridlines
    g.append('g')
      .call(d3.axisLeft(yScale).ticks(3).tickSize(-innerW).tickFormat((_d: d3.NumberValue) => ''))
      .call((ag: d3.Selection<SVGGElement, unknown, null, undefined>) => ag.select('.domain').remove())
      .call((ag: d3.Selection<SVGGElement, unknown, null, undefined>) => ag.selectAll('line')
        .attr('stroke', 'rgba(255,255,255,0.1)').attr('stroke-dasharray', '3,3'));

    const years = d3.range(Math.ceil(xMin), 2029);
    const qTicks = allQuarterlyTicks(xMin);

    // X-axis (year ticks initially)
    const xAxisG = g.append('g').attr('transform', `translate(0,${innerH})`)
      .call(d3.axisBottom(xScale)
        .tickValues(years)
        .tickFormat(d => String(d)))
      .call(ag => ag.selectAll('text')
        .attr('fill', '#9ca3af').attr('font-size', '9')
        .attr('transform', 'rotate(-35)')
        .attr('text-anchor', 'end')
        .attr('dy', '0.4em'))
      .call(ag => ag.selectAll('line,path').attr('stroke', '#4b5563'));

    // Y axis
    g.append('g')
      .call(d3.axisLeft(yScale).ticks(3).tickFormat(d => d3.format('.3f')(Number(d))))
      .call(ag => ag.selectAll('text').attr('fill', '#9ca3af').attr('font-size', '9'))
      .call(ag => ag.selectAll('line,path').attr('stroke', '#4b5563'));

    g.append('text')
      .attr('transform', 'rotate(-90)')
      .attr('x', -innerH / 2).attr('y', -MARGIN.left + 14)
      .attr('text-anchor', 'middle').attr('fill', '#6b7280').attr('font-size', '9')
      .text('Acc./Ship-Quarter');

    // Overlay for zoom. Draw it below the chart so visible points remain clickable.
    const overlay = g.append('rect')
      .attr('width', innerW).attr('height', innerH)
      .attr('fill', 'none').attr('pointer-events', 'all');

    const chartG = g.append('g').attr('clip-path', `url(#${CLIP_ID})`);

    const makeArea = (xFn: (d: QuarterlyPoint) => number) =>
      d3.area<QuarterlyPoint>()
        .x(xFn).y0(innerH).y1(d => yScale(d.accident_rate))
        .curve(d3.curveMonotoneX);

    const makeLine = (xFn: (d: QuarterlyPoint) => number) =>
      d3.line<QuarterlyPoint>()
        .x(xFn).y(d => yScale(d.accident_rate))
        .curve(d3.curveMonotoneX);

    const xFn0 = (d: QuarterlyPoint) => xScale(d.x);

    const areaPath = chartG.append('path').datum(points)
      .attr('d', makeArea(xFn0)(points) ?? '')
      .attr('fill', 'rgba(170,59,255,0.12)')
      .attr('pointer-events', 'none');

    const linePath = chartG.append('path').datum(points)
      .attr('d', makeLine(xFn0)(points) ?? '')
      .attr('fill', 'none').attr('stroke', '#aa3bff').attr('stroke-width', 1.5)
      .attr('pointer-events', 'none');

    const dots = chartG.selectAll<SVGCircleElement, QuarterlyPoint>('circle.hist')
      .data(points).join('circle')
      .attr('class', 'hist')
      .attr('cx', d => xScale(d.x))
      .attr('cy', d => yScale(d.accident_rate))
      .attr('r', 3)
      .attr('fill', '#aa3bff').attr('stroke', '#fff').attr('stroke-width', 1)
      .style('cursor', 'default');

    // Prediction: 3 lines (ci_upper, accident_rate, ci_lower) + connector + dots
    const makePredLine = (yFn: (d: PredictedYearlyPoint) => number, xFn = (d: PredictedYearlyPoint) => xScale(d.year)) =>
      d3.line<PredictedYearlyPoint>().x(xFn).y(yFn).curve(d3.curveMonotoneX);

    // Connector: last historical quarterly point → first prediction point
    const lastPoint = points[points.length - 1];
    const connectorData: Array<{ x: number; y: number }> = predicted.length > 0 && lastPoint
      ? [
          { x: lastPoint.x,       y: lastPoint.accident_rate },
          { x: predicted[0].year, y: predicted[0].accident_rate },
        ]
      : [];

    const connectorLine = d3.line<{ x: number; y: number }>()
      .x(d => xScale(d.x))
      .y(d => yScale(d.y))
      .curve(d3.curveMonotoneX);

    const appendPredPath = (yFn: (d: PredictedYearlyPoint) => number, dasharray: string) =>
      chartG.append('path')
        .datum(predicted)
        .attr('d', makePredLine(yFn)(predicted) ?? '')
        .attr('fill', 'none')
        .attr('stroke', '#fbbf24')
        .attr('stroke-width', 1.5)
        .attr('stroke-dasharray', dasharray)
        .attr('pointer-events', 'none');

    const predConnector = chartG.append('path')
      .datum(connectorData)
      .attr('d', connectorLine(connectorData) ?? '')
      .attr('fill', 'none')
      .attr('stroke', '#fbbf24')
      .attr('stroke-width', 1.5)
      .attr('stroke-dasharray', '5,3')
      .attr('pointer-events', 'none');

    const predLinePath  = appendPredPath(d => yScale(d.accident_rate),  '5,3');

    const predDots = chartG.selectAll<SVGCircleElement, PredictedYearlyPoint>('circle.pred')
      .data(predicted).join('circle')
      .attr('class', 'pred')
      .attr('cx', d => xScale(d.year))
      .attr('cy', d => yScale(d.accident_rate))
      .attr('r', 3)
      .attr('fill', '#fbbf24').attr('stroke', '#fff').attr('stroke-width', 1)
      .style('cursor', 'default');

    function applyAxisStyle(axisG: d3.Selection<SVGGElement, unknown, null, undefined>) {
      axisG
        .call((ag: d3.Selection<SVGGElement, unknown, null, undefined>) => ag.selectAll('text')
          .attr('fill', '#9ca3af').attr('font-size', '9')
          .attr('transform', 'rotate(-35)').attr('text-anchor', 'end').attr('dy', '0.4em'))
        .call((ag: d3.Selection<SVGGElement, unknown, null, undefined>) => ag.selectAll('line,path').attr('stroke', '#4b5563'));
    }

    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([1, 20])
      .extent([[0, 0], [innerW, innerH]])
      .translateExtent([[0, 0], [innerW, innerH]])
      .on('zoom', (event: d3.D3ZoomEvent<SVGSVGElement, unknown>) => {
        const newX = event.transform.rescaleX(xScale);
        const xFnNew = (d: QuarterlyPoint) => newX(d.x);

        // Switch tick granularity based on visible x-range
        const visibleRange = (newX.invert(innerW) - newX.invert(0));
        if (visibleRange <= QUARTERLY_THRESHOLD) {
          // Quarterly ticks — only those in the visible window
          const visMin = newX.invert(0);
          const visMax = newX.invert(innerW);
          const visibleQTicks = qTicks.filter(t => t >= visMin - 0.25 && t <= visMax + 0.25);
          applyAxisStyle(
            xAxisG.call(d3.axisBottom(newX)
              .tickValues(visibleQTicks)
              .tickFormat((d: d3.NumberValue) => quarterLabel(Number(d))))
          );
        } else {
          // Yearly ticks
          applyAxisStyle(
            xAxisG.call(d3.axisBottom(newX)
              .tickValues(years)
              .tickFormat((d: d3.NumberValue) => String(d)))
          );
        }

        areaPath.attr('d', makeArea(xFnNew)(points) ?? '');
        linePath.attr('d', makeLine(xFnNew)(points) ?? '');
        dots.attr('cx', d => newX(d.x));

        const makePredLineZoom = (yFn: (d: PredictedYearlyPoint) => number) =>
          d3.line<PredictedYearlyPoint>().x(d => newX(d.year)).y(yFn).curve(d3.curveMonotoneX);
        const connectorLineZoom = d3.line<{ x: number; y: number }>()
          .x(d => newX(d.x)).y(d => yScale(d.y)).curve(d3.curveMonotoneX);

        predConnector.attr('d', connectorLineZoom(connectorData) ?? '');
        predLinePath .attr('d', makePredLineZoom(d => yScale(d.accident_rate))(predicted) ?? '');
        predDots.attr('cx', d => newX(d.year));

        if (resetBtn) {
          const isDefault = event.transform.k === 1 && event.transform.x === 0;
          resetBtn.style.display = isDefault ? 'none' : 'block';
        }
      });

    zoomRef.current = zoom;
    overlay.call(zoom as unknown as (sel: d3.Selection<SVGRectElement, unknown, null, undefined>) => void);

  }, [currentCountry, trendByFlag]);

  const handleReset = () => {
    const svg = svgRef.current;
    const container = containerRef.current;
    if (!svg || !container || !zoomRef.current) return;
    const overlay = d3.select(svg).select<SVGRectElement>('rect[pointer-events="all"]');
    if (!overlay.empty()) {
      overlay.transition().duration(300)
        .call((zoomRef.current as unknown as d3.ZoomBehavior<SVGRectElement, unknown>).transform, d3.zoomIdentity);
    }
  };

  if (!currentCountry) return null;
  const noData = !loading && !trendByFlag.get(currentCountry);

  return (
    <div ref={containerRef} className='trend-container'>
      <div className='trend-title-row'>
        <span className='trend-title'>Accident Rate Trend (Quarterly)</span>
        <button ref={resetBtnRef} className='trend-reset-btn' style={{ display: 'none' }} onClick={handleReset}>
          Reset zoom
        </button>
      </div>
      {loading  && <div className='trend-loading'>Loading trend data…</div>}
      {noData   && <div className='trend-loading'>No trend data for {currentCountry}</div>}
      <svg ref={svgRef} />
    </div>
  );
}

export default TrendComponent;
