const chartContainer = document.getElementById("tvchart");
const symbolSelect = document.getElementById("symbolSelect");
const intervalSelect = document.getElementById("intervalSelect");
const loadChartBtn = document.getElementById("loadChartBtn");
const activeSymbolLabel = document.getElementById("activeSymbolLabel");
const activeIntervalLabel = document.getElementById("activeIntervalLabel");
const brokerHealthLabel = document.getElementById("brokerHealthLabel");

let chart;
let candleSeries;

function createChart() {
    chartContainer.innerHTML = "";

    chart = LightweightCharts.createChart(chartContainer, {
        layout: {
            background: { color: "#0b1120" },
            textColor: "#cbd5e1",
        },
        grid: {
            vertLines: { color: "#1e293b" },
            horzLines: { color: "#1e293b" },
        },
        width: chartContainer.clientWidth,
        height: chartContainer.clientHeight,
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
        },
        rightPriceScale: {
            borderColor: "#334155",
        },
        timeScale: {
            borderColor: "#334155",
            timeVisible: true,
            secondsVisible: false,
        },
    });

    candleSeries = chart.addCandlestickSeries({
        upColor: "#22c55e",
        downColor: "#ef4444",
        borderVisible: false,
        wickUpColor: "#22c55e",
        wickDownColor: "#ef4444",
    });
}

async function loadCandles(symbol, interval) {
    const url = `${window.APP_CONFIG.candlesApiUrl}?symbol=${encodeURIComponent(symbol)}&interval=${encodeURIComponent(interval)}`;
    const response = await fetch(url);
    const data = await response.json();

    if (data.status && Array.isArray(data.candles)) {
        candleSeries.setData(data.candles);
        activeSymbolLabel.textContent = data.symbol;
        activeIntervalLabel.textContent = data.interval;
    }
}

async function loadBrokerHealth() {
    try {
        const response = await fetch(window.APP_CONFIG.brokerHealthUrl);
        const data = await response.json();
        brokerHealthLabel.textContent = data.status ? "Connected" : "Not Connected";
    } catch (error) {
        brokerHealthLabel.textContent = "Health Check Failed";
    }
}

function applyChart() {
    const symbol = symbolSelect.value;
    const interval = intervalSelect.value;
    loadCandles(symbol, interval);
}

loadChartBtn.addEventListener("click", applyChart);

window.addEventListener("resize", () => {
    if (chart) {
        chart.applyOptions({
            width: chartContainer.clientWidth,
            height: chartContainer.clientHeight,
        });
    }
});

createChart();
loadCandles(window.APP_CONFIG.symbol, window.APP_CONFIG.interval);
loadBrokerHealth();