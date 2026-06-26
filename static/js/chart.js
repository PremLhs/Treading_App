const chartContainer = document.getElementById("tvchart");
const symbolSelect = document.getElementById("symbol");
const intervalSelect = document.getElementById("interval");
const activeSymbolLabel = document.getElementById("activeSymbolLabel");
const activeIntervalLabel = document.getElementById("activeIntervalLabel");
const brokerHealthLabel = document.getElementById("brokerHealthLabel");
const recordsLabel = document.getElementById("recordsLabel");
const chartStatusText = document.getElementById("chartStatusText");
const lastCandleTime = document.getElementById("lastCandleTime");
const backendMessage = document.getElementById("backendMessage");
const indicatorChartsWrap = document.getElementById("indicatorChartsWrap");
const chartShell = document.getElementById("chartShell");

const btnRefresh = document.getElementById("btnRefresh");
const btnFit = document.getElementById("btnFit");
const btnResetZoom = document.getElementById("btnResetZoom");
const btnScreenshot = document.getElementById("btnScreenshot");
const btnFullscreen = document.getElementById("btnFullscreen");
const toggleEMA20Btn = document.getElementById("toggleEMA20");
const toggleEMA50Btn = document.getElementById("toggleEMA50");
const toggleRSIBtn = document.getElementById("toggleRSI");
const toggleMACDBtn = document.getElementById("toggleMACD");
const toggleAmavasyaBtn = document.getElementById("toggleAmavasya");
const ohlcInfo = document.getElementById("ohlcInfo");

let chart = null;
let candleSeries = null;
let ema20Series = null;
let ema50Series = null;

let rsiChart = null;
let rsiSeries = null;

let macdChart = null;
let macdLineSeries = null;
let macdSignalSeries = null;
let macdHistogramSeries = null;

let refreshTimer = null;
let isLoadingCandles = false;
let isLoadingAmavasya = false;
let hasFittedInitially = false;

let amavasyaPriceLines = [];
let amavasyaLevelsCacheKey = null;

let indicatorsState = {
    ema20: true,
    ema50: true,
    rsi: true,
    macd: true,
    amavasya: false,
};

let lastGoodState = {
    symbol: null,
    interval: null,
    candles: [],
};

function logInfo(label, payload = null) {
    if (payload !== null) {
        console.log(`[chart.js] ${label}`, payload);
    } else {
        console.log(`[chart.js] ${label}`);
    }
}

function logWarn(label, payload = null) {
    if (payload !== null) {
        console.warn(`[chart.js] ${label}`, payload);
    } else {
        console.warn(`[chart.js] ${label}`);
    }
}

function logError(label, error) {
    console.error(`[chart.js] ${label}`, error);
}

function setStatus(text) {
    if (chartStatusText) chartStatusText.textContent = text;
}

function ensureLibraryLoaded() {
    if (typeof LightweightCharts === "undefined") {
        throw new Error("LightweightCharts library not loaded.");
    }
}

function getSelectedSymbol() {
    return symbolSelect ? symbolSelect.value : window.APP_CONFIG.symbol;
}

function getSelectedInterval() {
    return intervalSelect ? intervalSelect.value : window.APP_CONFIG.interval;
}

function clearAmavasyaLines() {
    if (!candleSeries || !Array.isArray(amavasyaPriceLines) || !amavasyaPriceLines.length) {
        amavasyaPriceLines = [];
        return;
    }

    amavasyaPriceLines.forEach(line => {
        try {
            candleSeries.removePriceLine(line);
        } catch (error) {
            logWarn("Failed to remove Amavasya price line", error);
        }
    });

    amavasyaPriceLines = [];
}

function clearExistingCharts() {
    clearAmavasyaLines();
    amavasyaLevelsCacheKey = null;

    try {
        if (chart) {
            chart.remove();
            chart = null;
        }
    } catch (error) {
        logWarn("Failed to remove main chart cleanly", error);
    }

    try {
        if (rsiChart) {
            rsiChart.remove();
            rsiChart = null;
        }
    } catch (error) {
        logWarn("Failed to remove RSI chart cleanly", error);
    }

    try {
        if (macdChart) {
            macdChart.remove();
            macdChart = null;
        }
    } catch (error) {
        logWarn("Failed to remove MACD chart cleanly", error);
    }

    candleSeries = null;
    ema20Series = null;
    ema50Series = null;
    rsiSeries = null;
    macdLineSeries = null;
    macdSignalSeries = null;
    macdHistogramSeries = null;

    if (indicatorChartsWrap) {
        indicatorChartsWrap.innerHTML = "";
    }
}

function createMainChart() {
    if (!chartContainer) {
        throw new Error("#tvchart container not found.");
    }

    ensureLibraryLoaded();

    chart = LightweightCharts.createChart(chartContainer, {
        width: chartContainer.clientWidth || 900,
        height: 560,
        layout: {
            background: { color: "#07111f" },
            textColor: "#cbd5e1",
        },
        grid: {
            vertLines: { color: "#162235" },
            horzLines: { color: "#162235" },
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
        },
        rightPriceScale: {
            borderColor: "#25354a",
        },
        timeScale: {
            borderColor: "#25354a",
            timeVisible: true,
            secondsVisible: false,
            rightOffset: 8,
            fixLeftEdge: false,
            fixRightEdge: false,
            barSpacing: 10,
        },
        localization: {
            locale: "en-IN",
            timeFormatter: (timestamp) => {
                return new Date(timestamp * 1000).toLocaleString("en-IN", {
                    timeZone: "Asia/Kolkata",
                    day: "2-digit",
                    month: "short",
                    year: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                    hour12: false,
                });
            },
        },
    });

    candleSeries = chart.addCandlestickSeries({
        upColor: "#16a34a",
        downColor: "#dc2626",
        borderVisible: false,
        wickUpColor: "#16a34a",
        wickDownColor: "#dc2626",
        priceLineVisible: true,
        lastValueVisible: true,
    });

    ema20Series = chart.addLineSeries({
        color: "#f59e0b",
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
        visible: indicatorsState.ema20,
    });

    ema50Series = chart.addLineSeries({
        color: "#38bdf8",
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
        visible: indicatorsState.ema50,
    });

    chart.subscribeCrosshairMove(param => {
        if (!param || !param.time) {
            if (ohlcInfo) ohlcInfo.innerHTML = "O: - | H: - | L: - | C: -";
            return;
        }

        const candle = param.seriesData.get(candleSeries);
        if (!candle) {
            if (ohlcInfo) ohlcInfo.innerHTML = "O: - | H: - | L: - | C: -";
            return;
        }

        if (ohlcInfo) {
            ohlcInfo.innerHTML = `O: ${candle.open.toFixed(2)} | H: ${candle.high.toFixed(2)} | L: ${candle.low.toFixed(2)} | C: ${candle.close.toFixed(2)}`;
        }
    });
}

function createIndicatorContainers() {
    if (!indicatorChartsWrap) {
        throw new Error("indicatorChartsWrap not found.");
    }

    indicatorChartsWrap.innerHTML = "";

    const rsiBox = document.createElement("div");
    rsiBox.id = "rsiChart";
    rsiBox.className = "indicator-box";

    const macdBox = document.createElement("div");
    macdBox.id = "macdChart";
    macdBox.className = "indicator-box indicator-box-macd";

    indicatorChartsWrap.appendChild(rsiBox);
    indicatorChartsWrap.appendChild(macdBox);

    rsiChart = LightweightCharts.createChart(rsiBox, {
        width: rsiBox.clientWidth || 900,
        height: 180,
        layout: {
            background: { color: "#07111f" },
            textColor: "#cbd5e1",
        },
        grid: {
            vertLines: { color: "#162235" },
            horzLines: { color: "#162235" },
        },
        rightPriceScale: {
            borderColor: "#25354a",
            scaleMargins: { top: 0.1, bottom: 0.1 },
        },
        timeScale: {
            borderColor: "#25354a",
            timeVisible: true,
            secondsVisible: false,
        },
    });

    rsiSeries = rsiChart.addLineSeries({
        color: "#a78bfa",
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
    });

    macdChart = LightweightCharts.createChart(macdBox, {
        width: macdBox.clientWidth || 900,
        height: 220,
        layout: {
            background: { color: "#07111f" },
            textColor: "#cbd5e1",
        },
        grid: {
            vertLines: { color: "#162235" },
            horzLines: { color: "#162235" },
        },
        rightPriceScale: {
            borderColor: "#25354a",
            scaleMargins: { top: 0.1, bottom: 0.1 },
        },
        timeScale: {
            borderColor: "#25354a",
            timeVisible: true,
            secondsVisible: false,
        },
    });

    macdLineSeries = macdChart.addLineSeries({
        color: "#22c55e",
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
    });

    macdSignalSeries = macdChart.addLineSeries({
        color: "#ef4444",
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
    });

    macdHistogramSeries = macdChart.addHistogramSeries({
        priceLineVisible: false,
        lastValueVisible: false,
        base: 0,
    });

    applyIndicatorVisibility();
}

function calculateEMA(data, period) {
    if (!Array.isArray(data) || data.length < period) return [];

    const k = 2 / (period + 1);
    const result = [];
    let ema = null;

    for (let i = 0; i < data.length; i++) {
        const close = Number(data[i].close);

        if (Number.isNaN(close)) continue;
        if (i < period - 1) continue;

        if (i === period - 1) {
            const sum = data
                .slice(0, period)
                .reduce((acc, item) => acc + Number(item.close || 0), 0);
            ema = sum / period;
        } else {
            ema = close * k + ema * (1 - k);
        }

        result.push({
            time: data[i].time,
            value: Number(ema.toFixed(2)),
        });
    }

    return result;
}

function calculateRSI(data, period = 14) {
    if (!Array.isArray(data) || data.length <= period) return [];

    const closes = data.map(item => Number(item.close));
    const rsi = [];
    let gains = 0;
    let losses = 0;

    for (let i = 1; i <= period; i++) {
        const diff = closes[i] - closes[i - 1];
        if (diff >= 0) gains += diff;
        else losses += Math.abs(diff);
    }

    let avgGain = gains / period;
    let avgLoss = losses / period;

    for (let i = period + 1; i < closes.length; i++) {
        const diff = closes[i] - closes[i - 1];
        const gain = diff > 0 ? diff : 0;
        const loss = diff < 0 ? Math.abs(diff) : 0;

        avgGain = ((avgGain * (period - 1)) + gain) / period;
        avgLoss = ((avgLoss * (period - 1)) + loss) / period;

        const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
        const value = 100 - (100 / (1 + rs));

        rsi.push({
            time: data[i].time,
            value: Number(value.toFixed(2)),
        });
    }

    return rsi;
}

function calculateMACD(data, fastPeriod = 12, slowPeriod = 26, signalPeriod = 9) {
    if (!Array.isArray(data) || data.length < slowPeriod) {
        return {
            macdLine: [],
            signalLine: [],
            histogram: [],
        };
    }

    const emaFast = calculateEMA(data, fastPeriod);
    const emaSlow = calculateEMA(data, slowPeriod);

    const slowMap = new Map(emaSlow.map(item => [item.time, item.value]));

    const macdRaw = emaFast
        .filter(item => slowMap.has(item.time))
        .map(item => ({
            time: item.time,
            value: Number((item.value - slowMap.get(item.time)).toFixed(2)),
        }));

    const macdAsCandles = macdRaw.map(item => ({
        time: item.time,
        close: item.value,
    }));

    const signal = calculateEMA(macdAsCandles, signalPeriod);
    const signalMap = new Map(signal.map(item => [item.time, item.value]));

    const macdLine = macdRaw.filter(item => signalMap.has(item.time));
    const signalLine = signal.filter(item => signalMap.has(item.time));

    const histogram = macdRaw
        .filter(item => signalMap.has(item.time))
        .map(item => {
            const hist = Number((item.value - signalMap.get(item.time)).toFixed(2));
            return {
                time: item.time,
                value: hist,
                color: hist >= 0 ? "#22c55e" : "#ef4444",
            };
        });

    return {
        macdLine,
        signalLine,
        histogram,
    };
}

function formatDateTime(timestamp) {
    if (!timestamp) return "-";

    return new Date(timestamp * 1000).toLocaleString("en-IN", {
        timeZone: "Asia/Kolkata",
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
    });
}

function normalizeCandles(candles) {
    if (!Array.isArray(candles)) return [];

    const map = new Map();

    candles.forEach(item => {
        if (
            item &&
            typeof item.time !== "undefined" &&
            typeof item.open !== "undefined" &&
            typeof item.high !== "undefined" &&
            typeof item.low !== "undefined" &&
            typeof item.close !== "undefined"
        ) {
            const t = Number(item.time);
            if (!Number.isFinite(t)) return;

            map.set(t, {
                time: t,
                open: Number(item.open),
                high: Number(item.high),
                low: Number(item.low),
                close: Number(item.close),
            });
        }
    });

    return Array.from(map.values()).sort((a, b) => a.time - b.time);
}

function buildAmavasyaLineTitle(level) {
    if (!level) return "Amavasya";

    const side = level.signal_type === "high_break" ? "AMV HIGH" : "AMV LOW";
    const refDate = level.reference_date || level.amavasya_calendar_date || "-";
    const triggerDate = level.trigger_date || "-";

    return `${side} | ${refDate} -> ${triggerDate}`;
}

function drawAmavasyaLines(levels) {
    clearAmavasyaLines();

    if (!candleSeries || !Array.isArray(levels) || !levels.length) {
        return;
    }

    levels.forEach(level => {
        const linePrice = Number(level.line_price);

        if (!Number.isFinite(linePrice)) {
            return;
        }

        try {
            const priceLine = candleSeries.createPriceLine({
                price: linePrice,
                color: level.line_color || (level.signal_type === "high_break" ? "#22c55e" : "#ef4444"),
                lineWidth: Number(level.line_width || 2),
                lineStyle: Number(level.line_style || 0),
                axisLabelVisible: true,
                title: buildAmavasyaLineTitle(level),
            });

            amavasyaPriceLines.push(priceLine);
        } catch (error) {
            logWarn("Failed to draw Amavasya line", { error, level });
        }
    });
}

async function loadAmavasyaStrategy(symbol, interval, options = {}) {
    const { silent = false } = options;

    if (!window.APP_CONFIG || !window.APP_CONFIG.amavasyaStrategyApiUrl) {
        logWarn("APP_CONFIG.amavasyaStrategyApiUrl missing.");
        return;
    }

    if (!indicatorsState.amavasya) {
        clearAmavasyaLines();
        amavasyaLevelsCacheKey = null;
        return;
    }

    if (isLoadingAmavasya) {
        return;
    }

    isLoadingAmavasya = true;

    try {
        if (!silent) {
            setStatus("Loading Amavasya...");
        }

        const strategyInterval = "15";
        const requestKey = `${symbol}__${strategyInterval}`;
        const url = `${window.APP_CONFIG.amavasyaStrategyApiUrl}?symbol=${encodeURIComponent(symbol)}&interval=${encodeURIComponent(strategyInterval)}`;

        const response = await fetch(url, {
            method: "GET",
            headers: {
                "X-Requested-With": "XMLHttpRequest",
                "Cache-Control": "no-cache",
            },
            cache: "no-store",
        });

        if (!response.ok) {
            throw new Error(`Amavasya API HTTP ${response.status}`);
        }

        const data = await response.json();
        logInfo("amavasya strategy response", data);

        if (!indicatorsState.amavasya) {
            clearAmavasyaLines();
            amavasyaLevelsCacheKey = null;
            return;
        }

        if (getSelectedSymbol() !== symbol) {
            logWarn("Skipping stale Amavasya response due to symbol change.");
            return;
        }

        if (data.status && Array.isArray(data.levels)) {
            drawAmavasyaLines(data.levels);
            amavasyaLevelsCacheKey = requestKey;
            if (backendMessage && !silent) {
                backendMessage.textContent = data.message || "Amavasya strategy loaded.";
            }
        } else {
            clearAmavasyaLines();
            amavasyaLevelsCacheKey = null;
            logWarn("Amavasya API returned empty or invalid data.", data);
            if (backendMessage && !silent) {
                backendMessage.textContent = data.message || "Amavasya levels not available.";
            }
        }

        if (!silent) {
            setStatus("Loaded");
        }
    } catch (error) {
        clearAmavasyaLines();
        amavasyaLevelsCacheKey = null;
        logError("loadAmavasyaStrategy failed", error);

        if (backendMessage && !silent) {
            backendMessage.textContent = `Amavasya load failed: ${error.message}`;
        }

        if (!silent) {
            setStatus("Loaded");
        }
    } finally {
        isLoadingAmavasya = false;
    }
}

function applyIndicatorVisibility() {
    if (ema20Series) ema20Series.applyOptions({ visible: indicatorsState.ema20 });
    if (ema50Series) ema50Series.applyOptions({ visible: indicatorsState.ema50 });

    const rsiBox = document.getElementById("rsiChart");
    const macdBox = document.getElementById("macdChart");

    if (rsiBox) rsiBox.style.display = indicatorsState.rsi ? "block" : "none";
    if (macdBox) macdBox.style.display = indicatorsState.macd ? "block" : "none";

    if (toggleEMA20Btn) toggleEMA20Btn.classList.toggle("active", indicatorsState.ema20);
    if (toggleEMA50Btn) toggleEMA50Btn.classList.toggle("active", indicatorsState.ema50);
    if (toggleRSIBtn) toggleRSIBtn.classList.toggle("active", indicatorsState.rsi);
    if (toggleMACDBtn) toggleMACDBtn.classList.toggle("active", indicatorsState.macd);
    if (toggleAmavasyaBtn) toggleAmavasyaBtn.classList.toggle("active", indicatorsState.amavasya);

    if (!indicatorsState.amavasya) {
        clearAmavasyaLines();
        amavasyaLevelsCacheKey = null;
    }

    resizeCharts();
}

function applySeriesData(candles, symbol, interval, apiMessage = "", meta = {}) {
    if (!chart || !candleSeries || !ema20Series || !ema50Series || !rsiSeries || !macdLineSeries || !macdSignalSeries || !macdHistogramSeries) {
        throw new Error("Chart series are not initialized.");
    }

    const cleanCandles = normalizeCandles(candles);
    candleSeries.setData(cleanCandles);

    const ema20 = calculateEMA(cleanCandles, 20);
    const ema50 = calculateEMA(cleanCandles, 50);
    const rsiData = calculateRSI(cleanCandles, 14);
    const macdData = calculateMACD(cleanCandles, 12, 26, 9);

    ema20Series.setData(ema20);
    ema50Series.setData(ema50);
    rsiSeries.setData(rsiData);
    macdLineSeries.setData(macdData.macdLine);
    macdSignalSeries.setData(macdData.signalLine);
    macdHistogramSeries.setData(macdData.histogram);

    if (activeSymbolLabel) activeSymbolLabel.textContent = symbol;
    if (activeIntervalLabel) activeIntervalLabel.textContent = interval;
    if (recordsLabel) recordsLabel.textContent = String(cleanCandles.length);
    if (backendMessage) backendMessage.textContent = apiMessage || "-";

    const last = cleanCandles[cleanCandles.length - 1];
    if (lastCandleTime) {
        lastCandleTime.textContent = last ? formatDateTime(last.time) : "-";
    }

    lastGoodState = {
        symbol,
        interval,
        candles: cleanCandles,
    };

    if (!hasFittedInitially) {
        chart.timeScale().fitContent();
        if (rsiChart) rsiChart.timeScale().fitContent();
        if (macdChart) macdChart.timeScale().fitContent();
        hasFittedInitially = true;
    }

    setStatus("Loaded");
    applyIndicatorVisibility();
}

async function loadCandles(symbol, interval, options = {}) {
    const { silent = false, forceFit = false } = options;

    if (isLoadingCandles) {
        if (!silent) {
            logWarn("Skipping candle fetch because previous request is still running.");
        }
        return;
    }

    if (!symbol || !interval) {
        logWarn("Symbol or interval missing for loadCandles");
        return;
    }

    isLoadingCandles = true;
    setStatus("Loading...");

    try {
        const url = `${window.APP_CONFIG.candlesApiUrl}?symbol=${encodeURIComponent(symbol)}&interval=${encodeURIComponent(interval)}`;
        const response = await fetch(url, {
            method: "GET",
            headers: {
                "X-Requested-With": "XMLHttpRequest",
                "Cache-Control": "no-cache",
            },
            cache: "no-store",
        });

        if (!response.ok) {
            throw new Error(`Candles API HTTP ${response.status}`);
        }

        const data = await response.json();
        logInfo("candles response", data);

        if (data.status && Array.isArray(data.candles) && data.candles.length > 0) {
            const symbolChanged = lastGoodState.symbol !== data.symbol;
            const intervalChanged = lastGoodState.interval !== data.interval;

            applySeriesData(
                data.candles,
                data.symbol,
                data.interval,
                data.message || "",
                data.meta || {}
            );

            if (indicatorsState.amavasya) {
                await loadAmavasyaStrategy(data.symbol, data.interval, { silent: true });
            } else {
                clearAmavasyaLines();
                amavasyaLevelsCacheKey = null;
            }

            if (forceFit || symbolChanged || intervalChanged) {
                chart.timeScale().fitContent();
                if (rsiChart) rsiChart.timeScale().fitContent();
                if (macdChart) macdChart.timeScale().fitContent();
            }
        } else {
            setStatus("No data");
            if (backendMessage) backendMessage.textContent = data.message || "No candle data returned.";
            logWarn("Candles API returned empty or invalid data. Keeping old chart.", data);
        }
    } catch (error) {
        setStatus("Failed");
        logError("loadCandles failed", error);
    } finally {
        isLoadingCandles = false;
    }
}

async function loadBrokerHealth() {
    if (!window.APP_CONFIG || !window.APP_CONFIG.brokerHealthUrl) {
        logWarn("brokerHealthUrl missing in APP_CONFIG");
        return;
    }

    try {
        const response = await fetch(window.APP_CONFIG.brokerHealthUrl, {
            method: "GET",
            headers: {
                "X-Requested-With": "XMLHttpRequest",
                "Cache-Control": "no-cache",
            },
            cache: "no-store",
        });

        if (!response.ok) {
            throw new Error(`Broker health HTTP ${response.status}`);
        }

        const data = await response.json();

        if (brokerHealthLabel) {
            brokerHealthLabel.textContent = data.status ? "Connected" : "Not Connected";
        }
    } catch (error) {
        logError("loadBrokerHealth failed", error);
        if (brokerHealthLabel) {
            brokerHealthLabel.textContent = "Health Check Failed";
        }
    }
}

function syncVisibleRange() {
    if (!chart || !rsiChart || !macdChart) return;

    const mainTimeScale = chart.timeScale();
    const rsiTimeScale = rsiChart.timeScale();
    const macdTimeScale = macdChart.timeScale();

    mainTimeScale.subscribeVisibleLogicalRangeChange(range => {
        if (!range) return;
        try {
            if (indicatorsState.rsi) {
                rsiTimeScale.setVisibleLogicalRange(range);
            }
            if (indicatorsState.macd) {
                macdTimeScale.setVisibleLogicalRange(range);
            }
        } catch (error) {
            logWarn("Visible range sync failed", error);
        }
    });
}

function resizeCharts() {
    if (chart && chartContainer) {
        chart.applyOptions({
            width: chartContainer.clientWidth || 900,
        });
    }

    const rsiBox = document.getElementById("rsiChart");
    const macdBox = document.getElementById("macdChart");

    if (rsiChart && rsiBox && indicatorsState.rsi) {
        rsiChart.applyOptions({
            width: rsiBox.clientWidth || 900,
        });
    }

    if (macdChart && macdBox && indicatorsState.macd) {
        macdChart.applyOptions({
            width: macdBox.clientWidth || 900,
        });
    }
}

function stopAutoRefresh() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
        refreshTimer = null;
    }
}

function startAutoRefresh() {
    stopAutoRefresh();

    refreshTimer = setInterval(() => {
        if (document.hidden) return;

        const selectedSymbol = getSelectedSymbol();
        const selectedInterval = getSelectedInterval();

        loadCandles(selectedSymbol, selectedInterval, { silent: true });
        loadBrokerHealth();
    }, 30000);
}

function downloadCanvasImage() {
    const canvas = chartContainer ? chartContainer.querySelector("canvas") : null;
    if (!canvas) {
        alert("Screenshot canvas not available.");
        return;
    }

    const link = document.createElement("a");
    link.href = canvas.toDataURL("image/png");
    link.download = `${getSelectedSymbol().replace(/[:]/g, "_")}_${getSelectedInterval()}_chart.png`;
    link.click();
}

async function toggleFullscreen() {
    if (!chartShell) return;

    try {
        if (!document.fullscreenElement) {
            await chartShell.requestFullscreen();
        } else {
            await document.exitFullscreen();
        }
        setTimeout(resizeCharts, 300);
    } catch (error) {
        logError("Fullscreen failed", error);
    }
}

function bindToolbarEvents() {
    if (btnRefresh) {
        btnRefresh.addEventListener("click", () => {
            loadCandles(getSelectedSymbol(), getSelectedInterval(), { forceFit: false });
            loadBrokerHealth();
        });
    }

    if (btnFit) {
        btnFit.addEventListener("click", () => {
            if (chart) chart.timeScale().fitContent();
            if (rsiChart && indicatorsState.rsi) rsiChart.timeScale().fitContent();
            if (macdChart && indicatorsState.macd) macdChart.timeScale().fitContent();
        });
    }

    if (btnResetZoom) {
        btnResetZoom.addEventListener("click", async () => {
            hasFittedInitially = false;
            if (lastGoodState.candles.length) {
                applySeriesData(
                    lastGoodState.candles,
                    lastGoodState.symbol,
                    lastGoodState.interval,
                    backendMessage ? backendMessage.textContent : ""
                );

                if (indicatorsState.amavasya) {
                    await loadAmavasyaStrategy(lastGoodState.symbol, lastGoodState.interval, { silent: true });
                }

                if (chart) chart.timeScale().fitContent();
                if (rsiChart && indicatorsState.rsi) rsiChart.timeScale().fitContent();
                if (macdChart && indicatorsState.macd) macdChart.timeScale().fitContent();
            }
        });
    }

    if (btnScreenshot) {
        btnScreenshot.addEventListener("click", downloadCanvasImage);
    }

    if (btnFullscreen) {
        btnFullscreen.addEventListener("click", toggleFullscreen);
    }

    if (toggleEMA20Btn) {
        toggleEMA20Btn.addEventListener("click", () => {
            indicatorsState.ema20 = !indicatorsState.ema20;
            applyIndicatorVisibility();
        });
    }

    if (toggleEMA50Btn) {
        toggleEMA50Btn.addEventListener("click", () => {
            indicatorsState.ema50 = !indicatorsState.ema50;
            applyIndicatorVisibility();
        });
    }

    if (toggleRSIBtn) {
        toggleRSIBtn.addEventListener("click", () => {
            indicatorsState.rsi = !indicatorsState.rsi;
            applyIndicatorVisibility();
        });
    }

    if (toggleMACDBtn) {
        toggleMACDBtn.addEventListener("click", () => {
            indicatorsState.macd = !indicatorsState.macd;
            applyIndicatorVisibility();
        });
    }

    if (toggleAmavasyaBtn) {
        toggleAmavasyaBtn.addEventListener("click", async () => {
            indicatorsState.amavasya = !indicatorsState.amavasya;
            applyIndicatorVisibility();

            if (indicatorsState.amavasya) {
                await loadAmavasyaStrategy(getSelectedSymbol(), getSelectedInterval(), { silent: false });
            } else {
                clearAmavasyaLines();
                amavasyaLevelsCacheKey = null;
                setStatus("Loaded");
            }
        });
    }
}

function bindEvents() {
    window.addEventListener("resize", resizeCharts);

    if (symbolSelect) {
        symbolSelect.addEventListener("change", () => {
            hasFittedInitially = false;
            loadCandles(getSelectedSymbol(), getSelectedInterval(), { forceFit: true });
        });
    }

    if (intervalSelect) {
        intervalSelect.addEventListener("change", () => {
            hasFittedInitially = false;
            loadCandles(getSelectedSymbol(), getSelectedInterval(), { forceFit: true });
        });
    }

    document.addEventListener("visibilitychange", () => {
        if (!document.hidden) {
            loadCandles(getSelectedSymbol(), getSelectedInterval(), { silent: true });
            loadBrokerHealth();
        }
    });

    document.addEventListener("fullscreenchange", () => {
        setTimeout(resizeCharts, 300);
    });

    bindToolbarEvents();
}

function validateAppConfig() {
    if (!window.APP_CONFIG) {
        throw new Error("window.APP_CONFIG is missing.");
    }

    if (!window.APP_CONFIG.candlesApiUrl) {
        throw new Error("APP_CONFIG.candlesApiUrl is missing.");
    }

    if (!window.APP_CONFIG.brokerHealthUrl) {
        throw new Error("APP_CONFIG.brokerHealthUrl is missing.");
    }

    if (!window.APP_CONFIG.amavasyaStrategyApiUrl) {
        throw new Error("APP_CONFIG.amavasyaStrategyApiUrl is missing.");
    }
}

async function initializeChartsApp() {
    validateAppConfig();
    ensureLibraryLoaded();
    clearExistingCharts();
    createMainChart();
    createIndicatorContainers();
    syncVisibleRange();
    bindEvents();
    resizeCharts();

    await loadCandles(window.APP_CONFIG.symbol, window.APP_CONFIG.interval, { forceFit: true });
    await loadBrokerHealth();
    startAutoRefresh();
}

document.addEventListener("DOMContentLoaded", async () => {
    try {
        await initializeChartsApp();
    } catch (error) {
        logError("Initialization failed", error);

        if (chartContainer) {
            chartContainer.innerHTML = `
                <div style="
                    display:flex;
                    align-items:center;
                    justify-content:center;
                    width:100%;
                    height:100%;
                    min-height:320px;
                    color:#f8fafc;
                    background:#07111f;
                    border:1px solid #1e293b;
                    border-radius:16px;
                    font-size:16px;
                    padding:24px;
                    text-align:center;
                ">
                    Chart failed to initialize. Check browser console and API response.
                </div>
            `;
        }
    }
});