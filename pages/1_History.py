import streamlit as st
import pandas as pd
from datetime import datetime
from fpl_engine import FPLMoneyLeague

# 1. PAGE SETUP
st.set_page_config(page_title="Sailors History", page_icon="📜", layout="wide")

# 2. INITIALIZE ENGINE
fpl = FPLMoneyLeague("126694")

# 3. CACHING FOR HISTORY
# We cache history for longer (e.g., 24 hours) since past data doesn't change
@st.cache_data(ttl=86400)
def get_historical_data(_fpl, gw):
    return _fpl.get_historical_standing(gw)

# --- UI START ---
st.title("📜 Sailors Historical Lookback")
st.write("Select a past Gameweek to review final rankings and tie-breakers.")

try:
    # We need the current GW just to set the limit for the selector
    current_gw, _, _ = fpl.get_gameweek_info()

    # SIDEBAR CONTROL
    st.sidebar.header("History Controls")
    selected_gw = st.sidebar.number_input(
        "Select Gameweek", 
        min_value=1, 
        max_value=current_gw, 
        value=current_gw - 1 if current_gw > 1 else 1, 
        step=1
    )

    st.divider()

    # FETCH DATA
    # In history, we don't necessarily need a button; it can update on change
    with st.spinner(f"Loading Gameweek {selected_gw} records..."):
        df = get_historical_data(fpl, selected_gw)

        if "Error" in df.columns:
            st.error(df["Error"].iloc[0])
        else:
            # Show the winner of that specific week
            top_row = df.iloc[0]
            st.success(f"🏆 **GW {selected_gw} Winner:** {top_row['Manager']} with {top_row['GW Points']} points!")

            # Currency Formatting
            def format_currency(val):
                return f"-${abs(val):.0f}" if val < 0 else f"${val:.0f}"

            # Apply identical styling to your Live page for consistency
            styled_df = df.style.format({'GW Cash': format_currency}) \
                .background_gradient(subset=['GW Cash'], cmap='RdYlGn')
            
            if 'Last 2 GW' in df.columns:
                styled_df = styled_df.set_properties(
                    subset=['Last 2 GW'], 
                    **{'color': '#ff4b4b', 'font-weight': 'bold'}
                )

            # Display
            st.dataframe(
                styled_df, 
                width='stretch',
                height=(len(df) + 1) * 35 + 3, 
                hide_index=True
            )

            st.caption(f"Historical record for Gameweek {selected_gw}. All points and hits are finalized.")

except Exception as e:
    st.warning(f"Unable to load history: {e}")