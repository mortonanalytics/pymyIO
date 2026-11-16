"""myDAR walk: plot the bundled iPhone walk and save the dashboard as HTML.

The walk is a real outdoor myDAR walk in local coordinates (the same data
R-myIO ships). Needs pandas: pip install 'pymyio[mydar]'.
"""

from pymyio.mydar import (
    mydar_dashboard,
    mydar_iphone_cloud,
    mydar_iphone_walk,
    mydar_plan_view,
    mydar_profile,
)

walk = mydar_iphone_walk()
print(walk)

# A profile line across the middle of the track.
ym = (walk.track["y"].min() + walk.track["y"].max()) / 2
line = {"from": (0, ym), "to": (22, ym)}
print(mydar_profile(walk, from_=line["from"], to=line["to"]).head())

plan = mydar_plan_view(walk, profile=line)
print([layer["label"] for layer in plan.to_config()["layers"]])

path = mydar_dashboard(walk, points=mydar_iphone_cloud(), profile=line).save("mydar-walk.html")
print("wrote", path)
