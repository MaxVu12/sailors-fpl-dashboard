import streamlit as st
import pandas as pd
import requests
import pytz
from datetime import datetime 


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
            1: 45, 
            2: 35, 
            3: 25, 
            4: 20, 
            5: 15, 
            6: 10, 
            7: 0, 
            8: -5, 
            9: -10, 
            10: -10, 
            11: -15, 
            12: -20, 
            13: -25, 
            14: -30, 
            15: -35
        }

    def get_gameweek_info(self):
        url = "https://fantasy.premierleague.com/api/bootstrap-static/"
        data = requests.get(url).json()
            
        events = data['events']
        current_gw = next((e for e in events if e['is_current']), events[0])
        next_gw = next((e for e in events if e['is_next']), None)
            
        deadline_to = "N/A"
        deadline_vn = "N/A"
            
        if next_gw:
            utc_time = datetime.strptime(next_gw['deadline_time'], '%Y-%m-%dT%H:%M:%SZ')
            utc_time = pytz.utc.localize(utc_time)
                    
            # Format for Toronto (Force 'EDT/EST' label)
            to_time = utc_time.astimezone(pytz.timezone('America/Toronto'))
            deadline_to = to_time.strftime('%b %d, %I:%M %p') + " EDT"
                    
            # Format for Hanoi (Force 'ICT' label)
            vn_time = utc_time.astimezone(pytz.timezone('Asia/Ho_Chi_Minh'))
            deadline_vn = vn_time.strftime('%b %d, %I:%M %p') + " ICT"
                    
        return current_gw['id'], deadline_to, deadline_vn

    def get_live_standings(self):
        # 1. Fetch current Gameweek dynamically
        gw_info = self.get_gameweek_info()
        current_gw = gw_info[0]

        data = get_data(self.api_url)

        # Check if 'standings' exists in the response
        if 'standings' not in data or not data['standings'].get('results'):
            return pd.DataFrame({"Error": ["League hasn't started or no results found yet."]})
            
        standings_results = data['standings']['results']
        all_manager_data = []
        
        # 2. Loop through managers to get Hits and Bench
        for entry in standings_results:
            team_id = entry['entry']
            
            # Call your cleaned-up history function
            gw_stats_df = self.calculate_team_gw_point(team_id, current_gw)
            gw_stats = gw_stats_df.iloc[0]
            
            all_manager_data.append({
                'Manager': entry['player_name'],
                'Team Name': entry['entry_name'],
                'GW Points': entry['event_total'],
                'Hits': int(gw_stats['transfers_cost']) * -1,
                'Bench': int(gw_stats['points_on_bench']),
                'OR': entry['rank'],
                'Total': entry['total']
            })

        df = pd.DataFrame(all_manager_data)

        df['GW Net'] = df['GW Points'] + df['Hits']

        # 3. SORTING LOGIC: Still using GW Points and Total for now
        df = df.sort_values(
            by=['GW Points', 'GW Net', 'Bench', 'Total'], 
            ascending=[False, False, False, False]
        )
        
        # 4. Create the Weekly Rank and Map Cash
        df['GW Rank'] = range(1, len(df) + 1)
        df['GW Cash'] = df['GW Rank'].map(self.weekly_prize_mapping).fillna(0)
        
        # 5. REORDER: Hits and Bench behind GW Cash
        column_order = [
            'GW Rank', 'Manager', 'Team Name', 'GW Points', 
            'GW Cash', 'Hits', 'Bench', 'OR', 'Total'
        ]

        return df[column_order]

    def calculate_team_gw_point(self, team_id, gw):
        """
        Fetches detailed GW stats for a specific manager to calculate tie-breakers.
        """
        url = f"https://fantasy.premierleague.com/api/entry/{team_id}/history/"
        
        try:
            response = requests.get(url)
            response.raise_for_status() # Check if the API call actually worked
            data = response.json()

            # Convert the 'current' season history to a DataFrame
            history = pd.DataFrame(data['current'])
            
            # Filter for the specific GW
            gw_row = history[history['event'] == gw]

            if gw_row.empty:
                # Return zeros if the manager didn't play that week
                return pd.DataFrame([{
                    'team_id': team_id, 'gw': gw, 'points': 0,
                    'points_on_bench': 0, 'transfers': 0, 'transfers_cost': 0
                }])

            gw_data = gw_row.iloc[0]

            # Return the clean stats needed for your tie-breaker logic
            return pd.DataFrame([{
                'team_id': team_id,
                'gw': gw,
                'points': int(gw_data['points']),
                'points_on_bench': int(gw_data['points_on_bench']),
                'transfers': int(gw_data['event_transfers']),
                'transfers_cost': int(gw_data['event_transfers_cost'])
            }])

        except Exception as e:
            # If the API is down or the ID is wrong, return a safe "empty" row
            return pd.DataFrame([{
                'team_id': team_id, 'gw': gw, 'points': 0,
                'points_on_bench': 0, 'transfers': 0, 'transfers_cost': 0
            }])

# --- STREAMLIT UI ---
st.set_page_config(page_title="Sailors FPL", page_icon="⚽")
st.title("⚓ Sailors FPL Money League")

# 1. Initialize class and fetch GW info immediately
fpl = FPLMoneyLeague("126694")

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
            
            st.write("### Gameweek Breakdown")

            # Custom function to fix the -$10 formatting
            def format_currency(val):
                if val < 0:
                    return f"-${abs(val):.0f}"
                return f"${val:.0f}"

            # Apply Styling
            styled_df = df.style.format({'GW Cash': format_currency}) \
                .background_gradient(subset=['GW Cash'], cmap='RdYlGn')

            # Display the table
            st.dataframe(
                styled_df, 
                width='stretch',
                height='stretch', 
                hide_index=True
            )
            
            # Timestamp
            st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %I:%M %p')} UTC")