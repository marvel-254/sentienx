"""
Performance Optimized CSS for SENTIENX Dashboard
"""

OPTIMIZED_CSS = """
<style>
/* Performance optimizations */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

html, body, [data-testid="stAppViewContainer"] {
    background-color: #0a0e27 !important;
    color: #e0e0e0 !important;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}

[data-testid="stSidebar"] {
    background-color: #1a1f3a !important;
}

.block-container {
    padding: 20px !important;
    background-color: #0a0e27 !important;
    max-width: 1600px;
    contain: layout style paint;
}

/* Responsive design */
@media (max-width: 768px) {
    .block-container {
        padding: 15px !important;
    }
    
    h1 {
        font-size: 24px !important;
    }
}

/* Tabs */
.stTabs [data-baseweb="tab"] {
    background-color: transparent;
    color: #94a3b8;
    padding: 12px 20px;
    transition: color 0.15s ease;
    cursor: pointer;
}

.stTabs [data-baseweb="tab"]:hover {
    color: #64c8ff;
}

/* Typography */
h1 {
    color: #00d4ff;
    margin-bottom: 20px;
    font-weight: 700;
    font-size: 28px;
}

h2 {
    color: #00d4ff;
    margin-top: 20px;
    margin-bottom: 15px;
    font-weight: 600;
}

/* Metrics */
.stMetric {
    background-color: #1a1f3a;
    padding: 15px;
    border-radius: 8px;
    border-left: 3px solid #00d4ff;
    transition: background-color 0.15s ease;
}

/* Buttons */
button {
    background-color: #2d3561 !important;
    color: #00d4ff !important;
    border: 1px solid #00d4ff !important;
    transition: all 0.15s ease;
    cursor: pointer;
    border-radius: 6px;
}

button:hover {
    background-color: #00d4ff !important;
    color: #0a0e27 !important;
    box-shadow: 0 0 12px rgba(0, 212, 255, 0.2);
}

/* Scrollbar */
::-webkit-scrollbar {
    width: 8px;
}

::-webkit-scrollbar-track {
    background: #0a0e27;
}

::-webkit-scrollbar-thumb {
    background: #2d3561;
    border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
    background: #3d4571;
}
</style>
"""

def get_optimized_css():
    return OPTIMIZED_CSS
