import streamlit as st
import pandas as pd
from datetime import datetime 
from fpl_engine import FPLMoneyLeague

# --- STREAMLIT UI ---
st.set_page_config(page_title="Sailors FPL", page_icon="⚽", layout="wide")

# 1. Initialize class and fetch GW info immediately
fpl = FPLMoneyLeague("126694")

# 2. CACHING LOGIC
# We wrap the engine call in a function so Streamlit can "save" the result
@st.cache_data(ttl=600)
def get_cached_standings(_fpl):
    return _fpl.get_live_standing()

st.title("⚓ Sailors FPL Money League")

# 3. GET HEADER GW AND DEADLINE
try:
    current_gw, deadline_to, deadline_vn = fpl.get_gameweek_info()
    next_gw = current_gw + 1
    
    # Using columns for the layout
    col_left, col_right = st.columns([1, 2])
    
    with col_left:
        # We use <h3> to match the "Next Deadline" header font family exactly
        st.markdown(
            f"""
            <div style="text-align: center;">
                <h3 style="margin-bottom: 0; font-weight: 600; opacity: 0.9;">Current GW</h3>
                <h1 style="margin-top: -10px; font-size: 3.5rem; font-weight: 800;">{current_gw}</h1>
            </div>
            """, 
            unsafe_allow_html=True
        )
        
    with col_right:
        st.markdown(f"### Next Deadline (GW {next_gw})")
        st.markdown(f"🇨🇦 **Toronto:** `{deadline_to}`")
        st.markdown(f"🇻🇳 **Hanoi:** `{deadline_vn}`")
    
    st.divider()

# 4. DATA FETCHING & DISPLAY
    if st.button('Fetch Live Standings'):
        with st.spinner('Calculating profits...'):
            # Use the cached function instead of fpl directly
            df = get_cached_standings(fpl)
            
            if "Error" in df.columns:
                st.error(df["Error"].iloc[0])
            else:
                # Metric for the weekly winner
                top_row = df.iloc[0]
                st.metric(
                    label="Current GW Leader", 
                    value=top_row['Manager'], 
                    delta=f"{top_row['GW Points']} pts"
                )
                
                st.write("### Gameweek Breakdown")

                # Custom function to fix the -$10 formatting
                def format_currency(val):
                    return f"-${abs(val):.0f}" if val < 0 else f"${val:.0f}"

                # Apply Styling
                styled_df = df.style.format({'GW Cash': format_currency}) \
                    .background_gradient(subset=['GW Cash'], cmap='RdYlGn')
                
                if 'Last 2 GW' in df.columns:
                    styled_df = styled_df.set_properties(
                        subset=['Last 2 GW'], 
                        **{'color': '#ff4b4b', 'font-weight': 'bold'}
                    )

                # Display the table
                st.dataframe(
                    styled_df, 
                    width="stretch",
                    height=(len(df) + 1) * 35 + 3, 
                    hide_index=True
                )
                
                # Timestamp
                st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %I:%M %p')} UTC")

except Exception as e:
    st.warning(f"Could not fetch status: {e}")