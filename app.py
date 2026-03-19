import streamlit as st
import pandas as pd
import requests
from datetime import datetime 
import pytz

# This keeps your app fast by not hitting the API on every single click
@st.cache_data(ttl=600) 
def get_data(url):
    return requests.get(url).json()

class FPLMoneyLeague:
    def __init__(self, league_id):
        self.league_id = league_id
        self.bootstrap_url = 'https://fantasy.premierleague.com/api/bootstrap-static/'
        self.api_url = f"https://fantasy.premierleague.com/api/leagues-classic/{self.league_id}/standings/"
        
        # Your specific money mapping
        self.weekly_prize_mapping = {
            1: 45, 2: 35, 3: 25, 4: 20, 5: 15, 6: 10, 7: 0, 
            8: -5, 9: -10, 10: -10, 11: -15, 12: -20, 13: -25, 14: -30, 15: -35
        }

    def get_live_standings(self):
        data = get_data(self.api_url)
            
        # DEBUG: This helps us see the actual API response if it fails
        # st.write(data) 

        # Check if 'standings' exists in the response
        if 'standings' not in data:
            return pd.DataFrame({"Error": ["Could not find standings. Check if your League ID is a Classic League."]})
            
        if not data['standings'].get('results'):
            return pd.DataFrame({"Error": ["League hasn't started or no results found yet."]})
            
        # Extract and rename initial columns
        df = pd.json_normalize(data['standings']['results'])
        df = df[['player_name', 'entry_name', 'event_total', 'rank', 'total']]
        df.columns = ['Manager', 'Team Name', 'GW Points', 'Overall Rank', 'Total Points']
            
        # LOGIC: Sort by GW performance for the Weekly Prizes
        df = df.sort_values(by=['GW Points', 'Total Points'], ascending=[False, False])
            
        # Create the Weekly Rank based on this sort
        df['Weekly Rank'] = range(1, len(df) + 1)
            
        # Calculate Cash
        df['Weekly Cash'] = df['Weekly Rank'].map(self.weekly_prize_mapping).fillna(0)
            
        # Reorder columns as requested
        column_order = [
            'Weekly Rank', 'Manager', 'Team Name', 
            'GW Points', 'Weekly Cash', 'Overall Rank', 'Total Points'
        ]

        return df[column_order]

    def get_gameweek_info(self):
        url = "https://fantasy.premierleague.com/api/bootstrap-static/"
        data = requests.get(url).json()
        
        events = data['events']
        next_gw = next((e for e in events if e['is_next']), None)
        
        # Return the raw string '2026-03-21T11:00:00Z'
        return next_gw['id'], next_gw['deadline_time'] if next_gw else None

# --- STREAMLIT UI ---
st.set_page_config(page_title="Sailors FPL", page_icon="⚽")
st.title("⚓ Sailors FPL Money League")

# 1. Initialize class and fetch raw GW info
fpl = FPLMoneyLeague("126694")

try:
    # Ensure your get_gameweek_info returns: current_gw_id, raw_utc_string
    current_gw, raw_deadline = fpl.get_gameweek_info()
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Current Gameweek", f"GW {current_gw}")
    with col2:
        # We use st.html to run JavaScript that detects the user's timezone
        st.write("**Next Deadline (Your Local Time)**")
        st.html(f"""
            <div style="background-color: #f0f2f6; padding: 10px; border-radius: 10px; border-left: 5px solid #ff4b4b;">
                <p id="deadline" style="font-family: sans-serif; font-size: 1.1rem; font-weight: bold; margin: 0; color: #31333F;">
                    Detecting time...
                </p>
                <p id="tz-name" style="font-family: sans-serif; font-size: 0.8rem; margin: 0; color: #555;">
                    --
                </p>
            </div>
            <script>
                const utcDate = "{raw_deadline}";
                if (utcDate && utcDate !== "None") {{
                    const localDate = new Date(utcDate);
                    const options = {{ 
                        month: 'short', 
                        day: 'numeric', 
                        hour: '2-digit', 
                        minute: '2-digit',
                        hour12: true 
                    }};
                    const tzName = Intl.DateTimeFormat().resolvedOptions().timeZone;
                    document.getElementById("deadline").innerHTML = localDate.toLocaleString(undefined, options);
                    document.getElementById("tz-name").innerHTML = "Timezone: " + tzName;
                }} else {{
                    document.getElementById("deadline").innerHTML = "No upcoming deadline";
                }}
            </script>
        """)
    
    st.divider()
except Exception as e:
    st.warning("Could not fetch current Gameweek status.")

# 2. The Button and Table Logic
if st.button('Fetch Live Standings'):
    with st.spinner('Calculating profits...'):
        df = fpl.get_live_standings()
        
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
            
            st.write("### Weekly Breakdown")

            # Custom function for currency
            def format_currency(val):
                if val < 0:
                    return f"-${abs(val):.0f}"
                return f"${val:.0f}"

            # Apply Styling
            styled_df = df.style.format({'Weekly Cash': format_currency}) \
                .background_gradient(subset=['Weekly Cash'], cmap='RdYlGn')

            # Display the table
            st.dataframe(
                styled_df, 
                width='stretch',
                height='content', 
                hide_index=True
            )
            
            # Timestamp (Local to Toronto/Server)
            st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %I:%M %p')} ET")