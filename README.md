# MySejahtera
Hotspot Center Locator for MySejahtera app

#####

Theoretically, this is possible to locate the center of hotspot if only 1 covid19 case around the area, by walking around the area and collect the `there have been 1 reported case(s) of COVID-19 within a 1km radius from your searched location in the last 14 days.` data. When no case means outside of the boundary of hotspot circle, while the 1 case means inside the hotspot. And eventually figure out the center of the hotspot. More than 1 cases possible too but complicated to me, so this program only try to solve 1 case.

The basic flow is, figure out direction west/east/north/south/southeast/northeast/northwest/southwest based on 1km outer of current position. Then walk straight on that direction from 500 M step until hit the 0 case or 1 case. Then fallback one step and retry with 500 M/2 = 250 M step, and until retry 6 CM step. Then walk the opposite side(I call 2 sides either of major(area) or minor(area) side) and repeat the walk steps. Then it get the chord line which can get a perpendicular line in the middle. Then repeat the 2 sides walk on that perpendicular line direction. Eventually it get diameter of hotspot circle, which can simply divide diameter by 2 to locate the center. To avoid false positive causes by outer has another hotspot, it also check <2 case in every step, and also distance of walk to ensure only walk 2km for that diameter. At the beginning, It also do checking 1km outer of current position to abort if >1 cases.
