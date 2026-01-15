"""
AML Score Visualization Module
Interactive Plotly dashboard for score analysis and event review
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import Optional, Dict, List


# =============================================================================
# COLOR SCHEMES
# =============================================================================

TIER_COLORS = {
    'HIGH': 'rgba(220, 53, 69, 0.9)',      # Red
    'MEDIUM': 'rgba(255, 193, 7, 0.9)',    # Orange/Yellow
    'LOW': 'rgba(40, 167, 69, 0.9)',       # Green
    'DEFAULT': 'rgba(108, 117, 125, 0.9)'  # Gray
}

TIER_FILL_COLORS = {
    'HIGH': 'rgba(220, 53, 69, 0.15)',
    'MEDIUM': 'rgba(255, 193, 7, 0.15)',
    'LOW': 'rgba(40, 167, 69, 0.15)',
    'DEFAULT': 'rgba(108, 117, 125, 0.1)'
}


# =============================================================================
# HOVER TEXT BUILDERS
# =============================================================================

def build_spike_hover_text(
    spike_date: pd.Timestamp,
    risk_tier: str,
    char_df: Optional[pd.DataFrame] = None,
    score_value: Optional[float] = None
) -> str:
    """
    Build compact hover text for spike markers.
    Shows: date, risk tier, top flags, volume change %
    """
    
    date_str = spike_date.strftime('%Y-%m-%d') if hasattr(spike_date, 'strftime') else str(spike_date)
    
    hover_lines = [
        f"<b>Event: {date_str}</b>",
        f"<b>Risk Tier: {risk_tier}</b>",
    ]
    
    if score_value is not None:
        hover_lines.append(f"Score: {score_value:.3f}")
    
    if char_df is not None and len(char_df) > 0:
        # Match on date - handle both datetime and string
        char_df = char_df.copy()
        if 'event_date' in char_df.columns:
            char_df['event_date'] = pd.to_datetime(char_df['event_date'])
            spike_date = pd.to_datetime(spike_date)
            char_row = char_df[char_df['event_date'].dt.date == spike_date.date()]
            
            if len(char_row) > 0:
                row = char_row.iloc[0]
                
                hover_lines.append("")  # Spacer
                
                # Top flags (max 3)
                flags = row.get('flag_types', '')
                if pd.notna(flags) and flags:
                    flag_list = str(flags).split(', ')[:3]
                    for flag in flag_list:
                        # Shorten flag names
                        short_flag = flag.replace('_', ' ').title()
                        hover_lines.append(f"• {short_flag}")
                
                hover_lines.append("")  # Spacer
                
                # Volume change
                vol_event = row.get('volume_event', 0)
                vol_baseline = row.get('volume_baseline', 0)
                if pd.notna(vol_baseline) and vol_baseline > 0:
                    vol_change = (vol_event - vol_baseline) / vol_baseline * 100
                    hover_lines.append(f"Volume: {vol_change:+.0f}%")
                
                # Transaction count
                txn_count = row.get('txn_count_event', 0)
                if pd.notna(txn_count):
                    hover_lines.append(f"Txns in window: {int(txn_count)}")
                
                # New counterparties
                new_cp = row.get('new_cp_count', 0)
                if pd.notna(new_cp) and new_cp > 0:
                    hover_lines.append(f"New counterparties: {int(new_cp)}")
    
    return '<br>'.join(hover_lines)


# =============================================================================
# MAIN DASHBOARD
# =============================================================================

def create_dashboard(
    scores_df: pd.DataFrame,
    events_df: pd.DataFrame,
    char_df: Optional[pd.DataFrame] = None,
    spike_threshold: Optional[float] = None,
    high_risk_threshold: float = 0.75,
    medium_risk_threshold: float = 0.5,
    lookback_days: int = 30,
    title: str = "AML Risk Score Dashboard",
    height: int = 500
) -> go.Figure:
    """
    Create interactive dashboard - single unified chart.
    
    Args:
        scores_df: DataFrame with columns:
            - date: observation date
            - raw_score: original risk score
            - rolling_max: rolling maximum (smoothed ratchet)
            - detrended: diff of rolling_max (first derivative)
        
        events_df: DataFrame with columns:
            - date: event date
            - is_spike: boolean flag for detected spikes
            - risk_tier: (optional) 'HIGH', 'MEDIUM', 'LOW'
        
        char_df: (optional) Characterization summary DataFrame
        
        spike_threshold: (optional) Threshold line for detrended (spike detection)
        
        high_risk_threshold: Score threshold for HIGH risk (default 0.75)
        
        medium_risk_threshold: Score threshold for MEDIUM risk (default 0.5)
        
        lookback_days: Days to shade before each spike event
        
        title: Dashboard title
        
        height: Figure height in pixels
    
    Returns:
        Plotly Figure object
    """
    
    # Ensure date columns are datetime
    scores_df = scores_df.copy()
    scores_df['date'] = pd.to_datetime(scores_df['date'])
    
    events_df = events_df.copy()
    events_df['date'] = pd.to_datetime(events_df['date'])
    
    # Create figure with secondary y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # =========================================================================
    # RISK TIER THRESHOLD BANDS (add first so they're behind everything)
    # =========================================================================
    
    # High risk band (top)
    fig.add_hrect(
        y0=high_risk_threshold, y1=1.0,
        fillcolor='rgba(220, 53, 69, 0.1)',
        line_width=0,
        layer='below',
        annotation_text='HIGH',
        annotation_position='top left',
        annotation=dict(font_size=10, font_color='rgba(220, 53, 69, 0.7)')
    )
    
    # Medium risk band (middle)
    fig.add_hrect(
        y0=medium_risk_threshold, y1=high_risk_threshold,
        fillcolor='rgba(255, 193, 7, 0.1)',
        line_width=0,
        layer='below',
        annotation_text='MEDIUM',
        annotation_position='top left',
        annotation=dict(font_size=10, font_color='rgba(255, 193, 7, 0.8)')
    )
    
    # Threshold lines
    fig.add_hline(
        y=high_risk_threshold,
        line_dash='dot',
        line_color='rgba(220, 53, 69, 0.5)',
        line_width=1
    )
    fig.add_hline(
        y=medium_risk_threshold,
        line_dash='dot',
        line_color='rgba(255, 193, 7, 0.6)',
        line_width=1
    )
    
    # =========================================================================
    # SPIKE LOOKBACK REGIONS (shaded areas before spikes)
    # =========================================================================
    
    spikes = events_df[events_df['is_spike'] == True].copy()
    
    for _, spike in spikes.iterrows():
        spike_date = pd.to_datetime(spike['date'])
        risk_tier = spike.get('risk_tier', 'DEFAULT')
        if pd.isna(risk_tier):
            risk_tier = 'DEFAULT'
        
        fill_color = TIER_FILL_COLORS.get(risk_tier, TIER_FILL_COLORS['DEFAULT'])
        lookback_start = spike_date - pd.Timedelta(days=lookback_days)
        
        fig.add_vrect(
            x0=lookback_start,
            x1=spike_date,
            fillcolor=fill_color,
            layer='below',
            line_width=0
        )
    
    # =========================================================================
    # SCORE LINES (primary y-axis)
    # =========================================================================
    
    # Raw score line
    fig.add_trace(
        go.Scatter(
            x=scores_df['date'],
            y=scores_df['raw_score'],
            mode='lines',
            name='Risk Score',
            line=dict(color='#1f77b4', width=2),
            hovertemplate='<b>%{x|%Y-%m-%d}</b><br>Score: %{y:.3f}<extra></extra>'
        ),
        secondary_y=False
    )
    
    # Rolling max line
    if 'rolling_max' in scores_df.columns:
        fig.add_trace(
            go.Scatter(
                x=scores_df['date'],
                y=scores_df['rolling_max'],
                mode='lines',
                name='Rolling Max',
                line=dict(color='#7f7f7f', width=1.5, dash='dash'),
                hovertemplate='<b>%{x|%Y-%m-%d}</b><br>Rolling Max: %{y:.3f}<extra></extra>'
            ),
            secondary_y=False
        )
    
    # =========================================================================
    # DETRENDED LINE (secondary y-axis)
    # =========================================================================
    
    if 'detrended' in scores_df.columns:
        fig.add_trace(
            go.Scatter(
                x=scores_df['date'],
                y=scores_df['detrended'],
                mode='lines',
                name='Detrended (Δ)',
                line=dict(color='#9467bd', width=1.5),
                opacity=0.7,
                hovertemplate='<b>%{x|%Y-%m-%d}</b><br>Detrended: %{y:.3f}<extra></extra>'
            ),
            secondary_y=True
        )
        
        # Spike detection threshold on secondary axis
        if spike_threshold is not None:
            fig.add_hline(
                y=spike_threshold,
                line_dash='dot',
                line_color='rgba(148, 103, 189, 0.7)',
                line_width=1,
                secondary_y=True,
                annotation_text=f'Spike threshold: {spike_threshold}',
                annotation_position='bottom right',
                annotation=dict(font_size=9, font_color='rgba(148, 103, 189, 0.9)')
            )
    
    # =========================================================================
    # SPIKE MARKERS
    # =========================================================================
    
    legend_added = set()
    
    for _, spike in spikes.iterrows():
        spike_date = pd.to_datetime(spike['date'])
        risk_tier = spike.get('risk_tier', 'DEFAULT')
        if pd.isna(risk_tier):
            risk_tier = 'DEFAULT'
        
        color = TIER_COLORS.get(risk_tier, TIER_COLORS['DEFAULT'])
        
        # Find score at spike date
        score_match = scores_df[scores_df['date'].dt.date == spike_date.date()]
        
        if len(score_match) == 0:
            continue
        
        score_val = score_match['raw_score'].values[0]
        
        # Build hover text
        hover_text = build_spike_hover_text(spike_date, risk_tier, char_df, score_val)
        
        # Legend handling
        show_in_legend = risk_tier not in legend_added
        if show_in_legend:
            legend_added.add(risk_tier)
        
        # Spike marker
        fig.add_trace(
            go.Scatter(
                x=[spike_date],
                y=[score_val],
                mode='markers',
                marker=dict(
                    symbol='triangle-up',
                    size=14,
                    color=color,
                    line=dict(width=1.5, color='white')
                ),
                name=f'{risk_tier} Risk Event',
                hovertext=hover_text,
                hoverinfo='text',
                showlegend=show_in_legend,
                legendgroup=risk_tier
            ),
            secondary_y=False
        )
    
    # =========================================================================
    # LAYOUT
    # =========================================================================
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=18)),
        height=height,
        hovermode='x unified',
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1,
            bgcolor='rgba(255,255,255,0.8)'
        ),
        margin=dict(t=80, b=50, l=60, r=60),
    )
    
    # Y-axis labels
    fig.update_yaxes(
        title_text='Risk Score',
        range=[0, 1.05],
        secondary_y=False
    )
    fig.update_yaxes(
        title_text='Detrended (Δ)',
        secondary_y=True,
        showgrid=False
    )
    
    # X-axis with range slider
    fig.update_xaxes(
        rangeslider=dict(visible=True, thickness=0.04)
    )
    
    return fig


# =============================================================================
# NOTEBOOK DISPLAY HELPERS
# =============================================================================

def display_dashboard(
    fig: go.Figure,
    char_df: Optional[pd.DataFrame] = None,
    events_df: Optional[pd.DataFrame] = None,
    show_table: bool = True
):
    """
    Display dashboard in Jupyter notebook with optional detail table.
    
    Args:
        fig: Plotly figure from create_dashboard
        char_df: Characterization summary for table display
        events_df: Events df to filter table to spikes only
        show_table: Whether to show the detail table
    """
    
    # Display figure
    fig.show()
    
    # Display table if requested
    if show_table and char_df is not None and len(char_df) > 0:
        from IPython.display import display, HTML
        
        display_df = char_df.copy()
        
        # Filter to spikes only if events_df provided
        if events_df is not None:
            spike_dates = events_df[events_df['is_spike'] == True]['date'].tolist()
            spike_dates = [pd.to_datetime(d).date() for d in spike_dates]
            display_df['event_date'] = pd.to_datetime(display_df['event_date'])
            display_df = display_df[display_df['event_date'].dt.date.isin(spike_dates)]
        
        # Select and order columns for display
        display_cols = [
            'user_id', 'event_date', 'risk_tier', 
            'flags_count', 'high_severity_count', 'flag_types',
            'txn_count_event', 'volume_event',
            'txn_size_ratio', 'velocity_ratio', 'credit_shift',
            'new_cp_count', 'new_cp_volume_share', 'top3_concentration'
        ]
        display_cols = [c for c in display_cols if c in display_df.columns]
        
        if len(display_cols) > 0:
            display_df = display_df[display_cols].copy()
            
            # Format numeric columns
            for col in ['txn_size_ratio', 'velocity_ratio', 'credit_shift', 
                       'new_cp_volume_share', 'top3_concentration']:
                if col in display_df.columns:
                    display_df[col] = display_df[col].apply(
                        lambda x: f'{x:.2f}' if pd.notna(x) and x != np.inf else '-'
                    )
            
            for col in ['volume_event']:
                if col in display_df.columns:
                    display_df[col] = display_df[col].apply(
                        lambda x: f'${x:,.0f}' if pd.notna(x) else '-'
                    )
            
            # Sort by event_date
            display_df = display_df.sort_values('event_date', ascending=False)
            
            display(HTML("<h3>Event Characterization Details</h3>"))
            display(display_df)


def create_single_user_dashboard(
    scores_df: pd.DataFrame,
    events_df: pd.DataFrame,
    char_df: Optional[pd.DataFrame] = None,
    user_id: Optional[str] = None,
    spike_threshold: Optional[float] = None,
    high_risk_threshold: float = 0.75,
    medium_risk_threshold: float = 0.5,
    lookback_days: int = 30
) -> go.Figure:
    """
    Convenience function for single-user analysis.
    Filters all dataframes to one user and creates dashboard.
    """
    
    if user_id is not None:
        if 'user_id' in scores_df.columns:
            scores_df = scores_df[scores_df['user_id'] == user_id]
        if 'user_id' in events_df.columns:
            events_df = events_df[events_df['user_id'] == user_id]
        if char_df is not None and 'user_id' in char_df.columns:
            char_df = char_df[char_df['user_id'] == user_id]
    
    title = f"AML Risk Score Dashboard - {user_id}" if user_id else "AML Risk Score Dashboard"
    
    return create_dashboard(
        scores_df=scores_df,
        events_df=events_df,
        char_df=char_df,
        spike_threshold=spike_threshold,
        high_risk_threshold=high_risk_threshold,
        medium_risk_threshold=medium_risk_threshold,
        lookback_days=lookback_days,
        title=title
    )


# =============================================================================
# EXAMPLE / TEST
# =============================================================================

if __name__ == "__main__":
    
    # Generate sample data
    np.random.seed(42)
    
    dates = pd.date_range('2025-01-01', periods=35, freq='W')
    
    # Simulate score that ramps up
    base_score = 0.3 + np.cumsum(np.random.normal(0.02, 0.03, 35))
    base_score = np.clip(base_score, 0, 1)
    
    # Rolling max (the ratchet)
    rolling_max = pd.Series(base_score).rolling(4, min_periods=1).max().values
    
    # Detrended = diff of rolling_max (first derivative of the ratchet)
    detrended = np.diff(rolling_max, prepend=rolling_max[0])
    
    scores_df = pd.DataFrame({
        'date': dates,
        'raw_score': base_score,
        'rolling_max': rolling_max,
        'detrended': detrended
    })
    
    # Simulate detected spikes
    events_df = pd.DataFrame({
        'date': dates,
        'is_spike': [False] * 8 + [True] + [False] * 10 + [True] + [False] * 8 + [True] + [False] * 6,
        'risk_tier': ['LOW'] * 8 + ['MEDIUM'] + ['LOW'] * 10 + ['HIGH'] + ['MEDIUM'] * 8 + ['HIGH'] + ['MEDIUM'] * 6
    })
    
    # Simulate characterization results
    spike_dates = events_df[events_df['is_spike']]['date'].tolist()
    char_df = pd.DataFrame({
        'event_date': spike_dates,
        'user_id': ['USER_001'] * len(spike_dates),
        'risk_tier': ['MEDIUM', 'HIGH', 'HIGH'],
        'flags_count': [2, 4, 3],
        'high_severity_count': [1, 3, 2],
        'flag_types': [
            'TRANSACTION_SIZE_INCREASE, CREDIT_HEAVY',
            'TRANSACTION_SIZE_INCREASE, VELOCITY_INCREASE, NEW_COUNTERPARTY_VOLUME, CONCENTRATION',
            'CREDIT_HEAVY, NEW_COUNTERPARTY_VOLUME, CONCENTRATION'
        ],
        'txn_count_event': [45, 78, 62],
        'volume_event': [125000, 450000, 320000],
        'volume_baseline': [80000, 120000, 150000],
        'txn_size_ratio': [1.8, 3.2, 2.5],
        'velocity_ratio': [1.5, 2.8, 2.1],
        'credit_shift': [0.18, 0.35, 0.22],
        'new_cp_count': [2, 5, 3],
        'new_cp_volume_share': [0.25, 0.45, 0.35],
        'top3_concentration': [0.65, 0.82, 0.75]
    })
    
    # Create dashboard
    fig = create_dashboard(
        scores_df=scores_df,
        events_df=events_df,
        char_df=char_df,
        spike_threshold=0.05,
        high_risk_threshold=0.75,
        medium_risk_threshold=0.5,
        lookback_days=30
    )
    
    # Save to HTML for testing
    fig.write_html('aml_dashboard_test.html')
    print("Dashboard saved to aml_dashboard_test.html")
    
    # Print sample hover text
    print("\nSample hover text for first spike:")
    print(build_spike_hover_text(spike_dates[0], 'MEDIUM', char_df))