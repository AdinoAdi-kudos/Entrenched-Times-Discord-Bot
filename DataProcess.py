import os
import pandas as pd
import numpy as np

# ------------------------------
# 1. Load data
# ------------------------------
script_dir = os.path.dirname(os.path.abspath(__file__))
file_name = "message_counts_20260429_103718.csv"
file_path = os.path.join(script_dir, file_name)

if not os.path.exists(file_path):
    print(f"ERROR: CSV file not found at {file_path}")
    exit()

df = pd.read_csv(file_path)

# ------------------------------
# 2. Clean Colour Roles
# ------------------------------
def split_roles(val):
    if pd.isna(val):
        return []
    if isinstance(val, str):
        val_stripped = val.strip()
        if val_stripped == "" or val_stripped.lower() == "none":
            return []
        roles = [r.strip() for r in val_stripped.split(",") if r.strip()]
        return roles
    return []

df['Colour_List'] = df['Colour Roles'].apply(split_roles)
df['Has_Any_Colour'] = df['Colour_List'].apply(lambda x: len(x) > 0)
df['Num_Colour_Roles'] = df['Colour_List'].apply(len)

# Exploded for per‑colour analysis (one row per user per colour)
exploded = df.explode('Colour_List').dropna(subset=['Colour_List'])
exploded.rename(columns={'Colour_List': 'Colour'}, inplace=True)

# ------------------------------
# 3. Overall comparison: any colour vs none
# ------------------------------
total_messages = df['Message Count'].sum()
total_users = len(df)

any_colour_stats = df.groupby('Has_Any_Colour')['Message Count'].agg(['sum', 'count', 'mean', 'median'])
any_colour_stats.columns = ['Total_Messages', 'User_Count', 'Mean_Messages', 'Median_Messages']
any_colour_stats['%_of_Users'] = 100 * any_colour_stats['User_Count'] / total_users
any_colour_stats['%_of_Messages'] = 100 * any_colour_stats['Total_Messages'] / total_messages
any_colour_stats.index = ['No Colour Role', 'Has Colour Role(s)']

print("\n" + "="*90)
print("OVERALL COMPARISON: USERS WITH COLOUR ROLES vs WITHOUT")
print("="*90)
print(any_colour_stats.round(2).to_string())
print("\n")

# ------------------------------
# 4. Per‑colour statistics (including thresholds)
# ------------------------------
# We'll use median as the threshold for "fitness" (can change to 25th percentile)
threshold_percentile = 0.50   # median; change to 0.25 for 25th percentile

colour_stats = exploded.groupby('Colour')['Message Count'].agg(['sum', 'count', 'mean', 'median'])
colour_stats.columns = ['Total_Messages', 'User_Count', 'Mean_Messages', 'Median_Messages']

# Add threshold (same as median here, but you could also use a fixed number or quantile)
colour_stats['Threshold'] = colour_stats['Median_Messages']   # can also use quantile

# Add percentage of all messages
colour_stats['%_of_All_Messages'] = 100 * colour_stats['Total_Messages'] / total_messages

# Sort by total messages descending for ranking
colour_stats = colour_stats.sort_values('Total_Messages', ascending=False)

print("="*90)
print("PER-COLOUR STATISTICS (sorted by total messages)")
print(f"Threshold = median message count of users with that colour")
print("="*90)
print(colour_stats.round(2).to_string())
print("\n")

# Extra comparison: which colour has highest avg per user, highest median, etc.
print("="*90)
print("ADDITIONAL PER-COLOUR INSIGHTS")
print("="*90)
highest_total = colour_stats['Total_Messages'].idxmax()
highest_avg = colour_stats['Mean_Messages'].idxmax()
highest_median = colour_stats['Median_Messages'].idxmax()
most_users = colour_stats['User_Count'].idxmax()
print(f"Colour with most total messages: {highest_total} ({colour_stats.loc[highest_total, 'Total_Messages']:,.0f} messages)")
print(f"Colour with highest average messages per user: {highest_avg} ({colour_stats.loc[highest_avg, 'Mean_Messages']:.1f} avg)")
print(f"Colour with highest median messages per user: {highest_median} ({colour_stats.loc[highest_median, 'Median_Messages']:.0f} median)")
print(f"Colour with most users: {most_users} ({colour_stats.loc[most_users, 'User_Count']} users)")
print("\n")

# ------------------------------
# 4b. Single-colour vs Mixed-colour users (within those with any role)
# ------------------------------
df['Is_Mixed_Role'] = df['Num_Colour_Roles'] > 1
users_with_role = df[df['Has_Any_Colour']].copy()

if len(users_with_role) > 0:
    mixed_comparison = users_with_role.groupby('Is_Mixed_Role')['Message Count'].agg(['sum', 'count', 'mean', 'median'])
    mixed_comparison.columns = ['Total_Messages', 'User_Count', 'Mean_Messages', 'Median_Messages']
    mixed_comparison['%_of_Role_Users'] = 100 * mixed_comparison['User_Count'] / len(users_with_role)
    mixed_comparison['%_of_Role_Messages'] = 100 * mixed_comparison['Total_Messages'] / users_with_role['Message Count'].sum()
    mixed_comparison.index = ['Single‑Colour Users', 'Mixed‑Colour Users (2+)']

    print("="*90)
    print("COMPARISON: SINGLE vs MIXED COLOUR USERS (within those with any role)")
    print("(Mixed = users with 2 or more colour roles)")
    print("NOTE: Per‑colour statistics already include mixed users correctly.")
    print("="*90)
    print(mixed_comparison.round(2).to_string())
    print("\n")

    # Optional: show which mixed users are extremely active or inactive
    mixed_users = users_with_role[users_with_role['Is_Mixed_Role']].copy()
    if not mixed_users.empty:
        print("="*90)
        print("TOP 5 MOST ACTIVE MIXED‑COLOUR USERS")
        print("="*90)
        top_mixed = mixed_users.nlargest(5, 'Message Count')[['User ID', 'Username', 'Num_Colour_Roles', 'Message Count', 'Colour Roles']]
        print(top_mixed.to_string(index=False))

        print("\n" + "="*90)
        print("BOTTOM 5 LEAST ACTIVE MIXED‑COLOUR USERS (possible over‑roling)")
        print("="*90)
        bottom_mixed = mixed_users.nsmallest(5, 'Message Count')[['User ID', 'Username', 'Num_Colour_Roles', 'Message Count', 'Colour Roles']]
        print(bottom_mixed.to_string(index=False))
        print("\n")
else:
    print("No users with colour roles found.\n")

# ------------------------------
# 5. Top 3 most active users per colour (with User ID)
# ------------------------------
def top_users_per_colour(df_exploded, colour_stats, top_n=3):
    """Return a dictionary: colour -> DataFrame with User ID, Username, Message Count"""
    results = {}
    for colour in colour_stats.index:
        subset = df_exploded[df_exploded['Colour'] == colour].copy()
        # Get the original User ID from the main df (we have it in exploded because explode keeps it)
        top_users = subset.nlargest(top_n, 'Message Count')[['User ID', 'Username', 'Message Count']]
        results[colour] = top_users.reset_index(drop=True)
    return results

top_per_colour = top_users_per_colour(exploded, colour_stats, top_n=3)

print("="*90)
print("TOP 3 MOST ACTIVE USERS PER COLOUR ROLE (with User ID)")
print("="*90)
for colour, top_df in top_per_colour.items():
    print(f"\n*** {colour} ***")
    if top_df.empty:
        print("  No users found.")
    else:
        # Print as formatted table
        for idx, row in top_df.iterrows():
            print(f"  {idx+1}. {row['Username']} (ID: {row['User ID']}) – {row['Message Count']:,} messages")
print("\n")

# ------------------------------
# 6. Unfit users: have a colour but below that colour's threshold (median)
# ------------------------------
unfit_records = []
for colour in colour_stats.index:
    thr = colour_stats.loc[colour, 'Threshold']
    # Get users with this colour and message count < threshold
    colour_users = exploded[exploded['Colour'] == colour].copy()
    unfit = colour_users[colour_users['Message Count'] < thr][['User ID', 'Username', 'Message Count', 'Colour Roles']]
    if not unfit.empty:
        unfit['Colour'] = colour
        unfit['Threshold'] = thr
        unfit_records.append(unfit)

if unfit_records:
    unfit_df = pd.concat(unfit_records, ignore_index=True)
    # Sort by Colour and then Message Count descending (to see the "least unfit" first)
    unfit_df = unfit_df.sort_values(['Colour', 'Message Count'], ascending=[True, False])
    print("="*90)
    print("UNFIT USERS (have a colour role but message count below that colour's median)")
    print("="*90)
    # Show selected columns
    print(unfit_df[['Colour', 'User ID', 'Username', 'Message Count', 'Threshold']].to_string(index=False))
else:
    print("No unfit users found.\n")

# ------------------------------
# 7. Users with multiple colour roles – fitness per role
# ------------------------------
# Get users who have more than one colour role
multi_role_users = df[df['Num_Colour_Roles'] > 1].copy()
if not multi_role_users.empty:
    print("="*90)
    print("USERS WITH MULTIPLE COLOUR ROLES")
    print("="*90)
    multi_summary = multi_role_users[['User ID', 'Username', 'Num_Colour_Roles', 'Message Count', 'Colour Roles']].copy()
    multi_summary = multi_summary.sort_values('Num_Colour_Roles', ascending=False)
    print(multi_summary.to_string(index=False))
    print("\n")

    # For each multi-role user, list which of their colours they are unfit for
    print("="*90)
    print("FITNESS PER ROLE FOR MULTI-COLOUR USERS")
    print("(Unfit = message count < that colour's median threshold)")
    print("="*90)
    
    # Re-use the unfit_df we created earlier, but filter only multi-role users
    if 'unfit_df' in locals() and not unfit_df.empty:
        # unfit_df already has columns: Colour, User ID, Username, Message Count, Threshold
        multi_unfit = unfit_df[unfit_df['User ID'].isin(multi_role_users['User ID'])].copy()
        if not multi_unfit.empty:
            # Group by user to show all unfit colours together
            for uid in multi_unfit['User ID'].unique():
                user_info = multi_role_users[multi_role_users['User ID'] == uid].iloc[0]
                print(f"\nUser: {user_info['Username']} (ID: {uid}) – Total Msgs: {user_info['Message Count']:,} – Total Roles: {user_info['Num_Colour_Roles']}")
                user_unfit = multi_unfit[multi_unfit['User ID'] == uid]
                if not user_unfit.empty:
                    print("  UNFIT for these colours (below threshold):")
                    for _, row in user_unfit.iterrows():
                        print(f"    - {row['Colour']}: msg={row['Message Count']:,} < threshold={row['Threshold']:.0f}")
                else:
                    print("  FIT for all their colours (above or equal median).")
        else:
            print("No multi-role users are unfit for any colour.")
    else:
        print("No unfit users found, so no multi-role users are unfit.")
else:
    print("\nNo users with multiple colour roles found.")

# ------------------------------
# 8. Potential candidates: users with NO colour role but high message count
# ------------------------------
no_role_users = df[~df['Has_Any_Colour']].copy()
if len(no_role_users) > 0:
    # Define high activity threshold = 90th percentile of no-role users
    high_threshold = no_role_users['Message Count'].quantile(0.90)
    candidates = no_role_users[no_role_users['Message Count'] >= high_threshold].copy()
    candidates = candidates.nlargest(20, 'Message Count')[['User ID', 'Username', 'Message Count']]
    print("="*90)
    print("POTENTIAL CANDIDATES FOR COLOUR ROLES (high activity, currently no colour role)")
    print(f"Threshold = 90th percentile of no-role group = {high_threshold:.0f} messages")
    print("(Top 20 users without any colour role, ordered by message count)")
    print("="*90)
    print(candidates.to_string(index=False))
else:
    print("No users without colour roles.\n")

# ------------------------------
# 8. (Optional) Summary: threshold comparison between groups
# ------------------------------
print("="*90)
print("THRESHOLD COMPARISON: Colour Role vs No Role")
print("="*90)
no_role_median = df[~df['Has_Any_Colour']]['Message Count'].median()
has_role_median = df[df['Has_Any_Colour']]['Message Count'].median()
print(f"Median messages for users with NO colour role: {no_role_median:.0f}")
print(f"Median messages for users with ANY colour role: {has_role_median:.0f}")
if has_role_median > no_role_median:
    print(f"→ Users with colour roles have a median {has_role_median - no_role_median:.0f} messages HIGHER than those without.")
else:
    print(f"→ Users with colour roles have a median {no_role_median - has_role_median:.0f} messages LOWER than those without.")
print("="*90)