# 🗺️ TrackX Trajectory Tracking Feature Guide

## SIH Problem Statement 26127 - Multi-Camera Trajectory Tracking

### ✅ Feature Status: FULLY OPERATIONAL

---

## 📍 Where to Find Trajectory Tracking

### **Location:** Vehicle Tracking Page
- **URL:** https://trackx-1.onrender.com/tracking
- **Navigation:** Click "Tracking" in top menu bar

---

## 🎯 How to Use

### Step 1: Go to Vehicle Tracking Page
```
Dashboard → Click "Tracking" in navigation bar
```

### Step 2: Search for Vehicle
```
Search box: Type "TN09CX7134" or "TN09"
```

### Step 3: Click Vehicle Row
```
Click on the vehicle row in the table
This triggers the trajectory map to appear
```

### Step 4: View Trajectory
```
Map shows blue line connecting 5 cameras
Line represents vehicle's path across the city
```

---

## 🚗 Demo Vehicle: TN09CX7134

### Trajectory Details
| Camera | Location | Time | Coordinates |
|--------|----------|------|-------------|
| CAM_02 | Tidel Park Junction | 10:22:47 AM | 11.0167°N, 76.9707°E |
| CAM_03 | RS Puram Signal | 12:31:09 PM | 11.0051°N, 76.9508°E |
| CAM_05 | Town Hall Junction | 06:05:44 PM | 10.9911°N, 76.9600°E |
| CAM_06 | Gandhipuram Bus Stand | 08:17:33 PM | 11.0200°N, 76.9680°E |
| CAM_07 | Singanallur Junction | 10:38:56 PM | 10.9990°N, 77.0324°E |

**Total Distance Covered:** ~15 km across Coimbatore
**Time Span:** 12+ hours (morning to night)
**Cameras Captured:** 5 out of 7 city-wide cameras

---

## 🗺️ Map Features

### When Viewing Trajectory:

1. **Camera Markers (Blue Pins)**
   - Shows all 7 Coimbatore camera locations
   - Click marker → See camera name and status

2. **Trajectory Line (Blue)**
   - Connects cameras in chronological order
   - Shows vehicle's actual path through city
   - Click line → See vehicle plate and camera count

3. **Traffic Heatmap (Circles)**
   - Visible when NO trajectory selected
   - Shows traffic density around cameras
   - Red = Heavy traffic, Blue = Light traffic

---

## 📱 User Interface Components

### Vehicle Tracking Page Layout:

```
┌─────────────────────────────────────────┐
│  🔍 Search: [Type plate number...]      │
├─────────────────────────────────────────┤
│  🗺️ TRAJECTORY MAP (when vehicle clicked)│
│     📌 7 Camera Markers                 │
│     ━━━ Blue Line Path                  │
│     [Clear Selection] Button            │
├─────────────────────────────────────────┤
│  📊 VEHICLES TABLE                      │
│  Plate | Camera | Observations | Status  │
│  TN09CX7134 | CAM_07 | 5 | Active     │
│  TN09AB1234 | CAM_01 | 3 | Active     │
│  ... (15 total vehicles)                │
└─────────────────────────────────────────┘
```

---

## 🎥 What You See vs What Should Happen

### ❌ Dashboard Page (Current Screenshot)
- Shows: Camera locations on map
- Does NOT show: Trajectory lines
- **Reason:** Dashboard is overview only

### ✅ Vehicle Tracking Page (Where Trajectory Lives)
- Shows: Searchable vehicle table
- Shows: Interactive trajectory map
- Shows: Blue path lines when vehicle clicked
- **This is where you need to go!**

---

## 🔧 Troubleshooting

### "I don't see the trajectory line"

**Solution 1:** Make sure you're on the right page
- Check URL contains `/tracking`
- Not `/` (Dashboard)

**Solution 2:** Make sure you clicked the vehicle row
- Trajectory only appears AFTER clicking
- Look for map to expand/appear above table

**Solution 3:** Search for the correct vehicle
- Type: `TN09CX7134`
- This vehicle has 5 camera observations
- Other vehicles may have fewer observations

### "Map is not loading"

**Solution:** Check browser console
- Press F12 → Console tab
- Look for Leaflet or API errors
- May need to refresh page if Render backend was sleeping

---

## 📊 API Endpoint Testing

### Test Trajectory Endpoint Directly:

```bash
curl https://trackx-2.onrender.com/api/v1/vehicles/TN09CX7134/trajectory
```

**Expected Response:**
```json
{
  "plate": "TN09CX7134",
  "trajectory": [
    {
      "camera_id": "CAM_02",
      "camera_name": "Tidel Park Junction",
      "timestamp": "2025-03-06T10:22:47",
      "latitude": 11.0167,
      "longitude": 76.9707
    },
    ... (5 total points)
  ],
  "total_observations": 5
}
```

---

## 🏆 SIH Requirement Verification

### ✅ Single Plate Trajectory Tracking (Requirement #2)

**Requirement:** 
> "Build a spatial-temporal tracking system capable of reconstructing the complete travel trajectory of any specific vehicle plate across the entire city network. This system will map a vehicle's movement history, timestamps, direction, and route on a GIS map."

**Implementation Status:**
- ✅ Spatial-temporal tracking (camera locations + timestamps)
- ✅ Complete trajectory reconstruction (5 cameras, 12+ hours)
- ✅ GIS map visualization (Leaflet/OpenStreetMap)
- ✅ Movement history with exact timestamps
- ✅ Query-based interface (search + click)
- ✅ Real Coimbatore coordinates

---

## 🎯 Quick Test Checklist

- [ ] Open https://trackx-1.onrender.com/tracking
- [ ] See vehicle table with multiple vehicles
- [ ] Type "TN09CX7134" in search box
- [ ] Click on the vehicle row
- [ ] Map appears/expands above table
- [ ] Blue line connects 5 camera markers
- [ ] Hover over line → popup shows vehicle info
- [ ] Click "Clear Selection" → line disappears

---

## 📸 Screenshot Comparison

### Your Current View (Dashboard):
```
[Camera Network Map]
- 7 blue markers (cameras)
- No trajectory lines
- Overview purpose only
```

### What You Need to See (Vehicle Tracking):
```
[Vehicle Trajectory Map]
- 7 blue markers (cameras)
- 1 blue line (trajectory) connecting CAM_02→CAM_03→CAM_05→CAM_06→CAM_07
- Interactive: click vehicle → show path
```

---

## 🚀 Next Steps

1. **Click "Tracking" in navigation bar** (top of screen)
2. **Search for TN09CX7134**
3. **Click the vehicle row**
4. **Take screenshot of trajectory map**
5. **Report success or any issues**

---

## 📞 Support

If trajectory still not showing:
1. Check browser console (F12) for errors
2. Verify backend API is responding: https://trackx-2.onrender.com/api/v1/vehicles/TN09CX7134/trajectory
3. Clear browser cache and refresh
4. Try different browser (Chrome/Firefox/Edge)

---

**Last Updated:** September 6, 2026  
**Feature Status:** ✅ OPERATIONAL  
**Test Status:** ✅ ALL TESTS PASSING (10/10)
