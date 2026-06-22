"""
Dashboard Enhancement – New metrics endpoints for the web dashboard.
"""
import logging
from typing import Dict, Any
from flask import Blueprint, jsonify, request

dashboard_bp = Blueprint('dashboard_enhanced', __name__, url_prefix='/api/enhanced')

# These will be injected by the main app
enhanced_risk_manager = None
regime_classifier = None
portfolio_optimizer = None
performance_analytics = None
early_warning = None

def init_enhanced_dashboard(risk_mgr, regime_clf, port_opt, perf_an, warn_sys):
    global enhanced_risk_manager, regime_classifier, portfolio_optimizer, performance_analytics, early_warning
    enhanced_risk_manager = risk_mgr
    regime_classifier = regime_clf
    portfolio_optimizer = port_opt
    performance_analytics = perf_an
    early_warning = warn_sys

@dashboard_bp.route('/risk/status')
def risk_status():
    """Return enhanced risk status."""
    if not enhanced_risk_manager:
        return jsonify({"error": "Risk manager not initialized"}), 503
    
    return jsonify({
        "current_capital": enhanced_risk_manager.current_capital,
        "peak_capital": enhanced_risk_manager.peak_capital,
        "drawdown_pct": (enhanced_risk_manager.peak_capital - enhanced_risk_manager.current_capital) / max(enhanced_risk_manager.peak_capital, 1) * 100,
        "var_95": enhanced_risk_manager.monte_carlo_var([]),  # Would need actual returns
        "consecutive_losses": enhanced_risk_manager._consecutive_losses,
        "is_halted": enhanced_risk_manager._is_halted
    })

@dashboard_bp.route('/regime/current')
def current_regime():
    """Return current market regime with details."""
    if not regime_classifier:
        return jsonify({"error": "Regime classifier not initialized"}), 503
    
    # This would need to be async in real implementation
    return jsonify({
        "regime": regime_classifier.current_regime,
        "parameters": regime_classifier.get_regime_parameters(),
        "last_update": "2026-06-22"  # TODO: actual timestamp
    })

@dashboard_bp.route('/portfolio/allocation')
def portfolio_allocation():
    """Return current portfolio allocation."""
    if not portfolio_optimizer:
        return jsonify({"error": "Portfolio optimizer not initialized"}), 503
    
    # In real implementation, would fetch actual bot performance
    return jsonify({
        "allocation": portfolio_optimizer.regime_allocations.get("neutral", {}),
        "regime": "neutral"
    })

@dashboard_bp.route('/performance/summary')
def performance_summary():
    """Return performance analytics summary."""
    if not performance_analytics:
        return jsonify({"error": "Performance analytics not initialized"}), 503
    
    return jsonify({
        "message": "Performance endpoint ready",
        "endpoints": [
            "/api/enhanced/performance/summary",
            "/api/enhanced/performance/metrics"
        ]
    })

@dashboard_bp.route('/alerts/early-warning')
def early_warning_alerts():
    """Return early warning system status."""
    if not early_warning:
        return jsonify({"error": "Early warning not initialized"}), 503
    
    return jsonify({
        "risk_score_threshold": early_warning.risk_score_limit,
        "volatility_threshold": early_warning.volatility_threshold,
        "liquidity_threshold": early_warning.liquidity_threshold,
        "status": "monitoring"
    })

@dashboard_bp.route('/health')
def health_check():
    """Comprehensive health check."""
    checks = {
        "risk_manager": enhanced_risk_manager is not None,
        "regime_classifier": regime_classifier is not None,
        "portfolio_optimizer": portfolio_optimizer is not None,
        "performance_analytics": performance_analytics is not None,
        "early_warning": early_warning is not None
    }
    
    all_healthy = all(checks.values())
    
    return jsonify({
        "status": "healthy" if all_healthy else "degraded",
        "components": checks,
        "timestamp": "2026-06-22"
    }), 200 if all_healthy else 503

# Example of how to integrate into main app:
"""
from services.dashboard_enhanced import dashboard_bp, init_enhanced_dashboard

# In main app initialization:
init_enhanced_dashboard(
    risk_mgr=advanced_risk_manager,
    regime_clf=regime_classifier,
    port_opt=portfolio_optimizer,
    perf_an=performance_analytics,
    warn_sys=early_warning
)

app.register_blueprint(dashboard_bp)
"""