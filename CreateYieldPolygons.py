import Tools.Functions
import Tools.Functions as f

import os, sys
import math
import arcpy

from importlib import reload
reload(Tools.Functions)


def load_yield_data(yield_layer, yield_fld, distance, direction, width):
	_yield_data = {}
	_yld_sr = arcpy.Describe(yield_layer).SpatialReference

	for row in arcpy.da.SearchCursor(yield_layer, ['OID@', 'SHAPE@XY', yield_fld.value, distance.value, direction.value, width.value]):
		pt_geom = arcpy.Point(float(row[1][0]), float(row[1][1]))
		_yield_data[row[0]] = { 				
			'oid': row[0],
			'pt': row[1],
            'yld': row[2],
			'dist': row[3],
			'dir': row[4],
			'width': row[5],
			'center_pt_geom': arcpy.PointGeometry(pt_geom, _yld_sr)
			} 	
	
	return(_yield_data, _yld_sr)    



# calculate the angle to a points (uses 0,0 as orgin) (0 = east unless rotation is specfied)
def angle_to(x, y, rotation=0, clockwise=False):
    angle = math.degrees(math.atan2(y, x)) - rotation
    if not clockwise:
        angle = -angle
    return angle % 360


# calculate the 4 - 90 degree angles from a heading (orgin is from 0,0)
def get_cardnal_dir_from_heading(azumthal_dir):
	_dir = {
		'front': azumthal_dir,
		'back': (azumthal_dir + 180) % 360,
		'left': (azumthal_dir -90) % 360,
		'right': (azumthal_dir + 90) % 360,
	}
	return(_dir)



def yld_polygon(yld_pt):
	_dir = get_cardnal_dir_from_heading(yld_pt['dir'])

	if(yld_pt['dist'] > 0 and yld_pt['width'] > 0):
		_um = yld_pt['center_pt_geom'].pointFromAngleAndDistance(_dir['front'],(yld_pt['dist_c']/2))	# upper middle of yield polygon
		_lm = yld_pt['center_pt_geom'].pointFromAngleAndDistance(_dir['back'],(yld_pt['dist_c']/2))		# low middle 

		_ul = _um.pointFromAngleAndDistance(_dir['left'],(yld_pt['width_c']/2))				# upper left
		_ur = _um.pointFromAngleAndDistance(_dir['right'],(yld_pt['width_c']/2))				# upper right

		_ll = _lm.pointFromAngleAndDistance(_dir['left'],(yld_pt['width_c']/2))			 	# lower left
		_lr = _lm.pointFromAngleAndDistance(_dir['right'],(yld_pt['width_c']/2))				# lower right

	_ulp = arcpy.Point(_ul.getPart(0).X, _ul.getPart(0).Y)
	_urp = arcpy.Point(_ur.getPart(0).X, _ur.getPart(0).Y)
	_llp = arcpy.Point(_ll.getPart(0).X, _ll.getPart(0).Y)
	_lrp = arcpy.Point(_lr.getPart(0).X, _lr.getPart(0).Y)
	
	poly = arcpy.Polygon(arcpy.Array([_ulp,_urp,_lrp,_llp]), yld_pt['center_pt_geom'].spatialReference)
	return(poly)


def printPtCoords(pt):
	f.tweet("{0} - {1}".format(pt.X, pt.Y), ap=arcpy)


def printArrayCoords(array_coords):
	for i in array_coords:
		printPtCoords(i)


# Create the polygons based on the yield points
def create_yield_polys(yld_data):
	for p, yld_pt in yld_data.items():
		yld_data[p]['poly_geom'] = yld_polygon(yld_pt)



#### create the new yield polygon layer
def create_layer(yld_data, toolparam, sr):
	f.tweet("Msg: Creating New Yield Layer...{0}\n".format(toolparam['output_layer'].value), ap=arcpy)
	
	file_path, file_name = os.path.split(toolparam['output_layer'].value)
	yld_poly_layer = arcpy.management.CreateFeatureclass(file_path, file_name, "POLYGON", spatial_reference=sr)
	
	fClass = yld_poly_layer[0]				 # return the path to the layer 

	arcpy.AddField_management(fClass, toolparam['yield_field'].value, "FLOAT")	
	arcpy.AddField_management(fClass, toolparam['swath_width'].value, "FLOAT")	
	arcpy.AddField_management(fClass, toolparam['swath_distance'].value, "FLOAT")	
			
	with arcpy.da.InsertCursor(fClass, ['SHAPE@', toolparam['yield_field'].value, toolparam['swath_width'].value, toolparam['swath_distance'].value]) as cursor:
		for oid, poly in yld_data.items():								 # loop through polygons inserting..
			cursor.insertRow([poly['poly_geom'], poly['yld'], poly['width'], poly['dist']])	
	
	del cursor
	return(fClass) 		



def convert_units(yld_data, conversion):
	for p, yld_pt in yld_data.items():
		yld_data[p]['width_c'] = yld_data[p]['width'] * conversion
		yld_data[p]['dist_c'] = yld_data[p]['dist'] * conversion



# This is used to execute code if the file was run but not imported
if __name__ == '__main__':

	FT_PER_METER = 0.30480060960121924
	METER_PER_FT = 1/FT_PER_METER

    # Get the parameters set in the Toolbox and in the current Map [yield_layer, yield_field, swath_distance, swath_direction, swath_width, points_per_poly, output_layer]
	_toolparam = f.get_tool_param()
	_mapparam = f.set_arcmap_param()  

	_yld_data, _yld_sr = load_yield_data(_toolparam['yield_layer'], 
 										_toolparam['yield_field'], 
 										_toolparam['swath_distance'],
										_toolparam['swath_direction'],
										_toolparam['swath_width']
	 									)

	# convert the width and distance to meters - don;t undestand why this is needed right now
	convert_units(_yld_data, FT_PER_METER)

	create_yield_polys(_yld_data)

	#f.tweet(_yld_data[1], ap=arcpy)

	create_layer(_yld_data, _toolparam, _yld_sr)

