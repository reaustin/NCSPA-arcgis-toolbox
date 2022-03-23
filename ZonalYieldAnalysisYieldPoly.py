import Tools.Functions
import Tools.Functions as f

import os, sys
import pandas as pd
import arcpy




if __name__ == '__main__':

    ZONE_FIELD = 'Zone'

    # Get the parameters set in the Toolbox and in the current Map 
    #   - [yield_polygons, yield_field, class_raster, dem_raster]
    _toolparam = f.get_tool_param()
    _mapparam = f.set_arcmap_param()  

    # set the output coordinate sysyem to NC Satteplance feet
    arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(2264)
    
    # set data about the yield layer and classified raster
    _yield_data = f.set_layer_data(_toolparam['yield_polygons'])
    _class_raster_data = f.set_raster_data(_toolparam['class_raster'])

    # Create a copy of the yield layer
    _yield_layer = os.path.join(_mapparam['gdb'], _yield_data['name'] + '_zs')
    arcpy.CopyFeatures_management(_yield_data['lyr'], _yield_layer)

    # Creating a zone field baseed on the ObjectId
    f.create_zone_field(_yield_layer, ZONE_FIELD)
    
    # calculate zone area
    arcpy.CalculateGeometryAttributes_management(_yield_layer, [["zone_area", "AREA"]])

    ### calculate the zonal statistics from the classifed raster - always use the 'Value' in the classifed raster - than layer merge with RAT
    _classstat_file = os.path.join(_mapparam['scratch'], _class_raster_data['name_base'] + "_zone_stat")
    _classstat_table = f.tabulate_area(_yield_layer, ZONE_FIELD, _class_raster_data['lyr'], _classstat_file)
    
    # if the classified raster has a RAT, then rename the columns based on the 'Class_name' field
    if(_class_raster_data['has_vat']):
        _new_column_names = f.map_values_to_classnames(_classstat_table, _class_raster_data['df'])
        f.calculate_percent_vegetation(_classstat_table, _new_column_names)

    # convert the table to a dataframe
    _classstat_df = f.table_to_data_frame(_classstat_table) 

    # clean up some columns
    f.drop_columns(_classstat_df, drop_columns=['shape', 'shape_length'])



    ### calculate the zonal stats from the elevation dataset 
    _stat_files = []
    if(_toolparam['dem_raster']):
        _dem_data = f.set_raster_data(_toolparam['dem_raster'])
        _demstat_file = _dem_data['name_base'] + "_dem_stat"
        _stat_files.append(_demstat_file)
        _demstat_filepath = os.path.join(_mapparam['scratch'], _demstat_file)
        _demstat_table = f.zonal_statistics(_yield_layer, ZONE_FIELD, _toolparam['dem_raster'], _demstat_filepath)

        _drop_fields = ['COUNT', 'AREA', 'MIN', 'MAX', 'SUM', 'PCT90']
        arcpy.DeleteField_management(_demstat_table, _drop_fields)
        
        _stat_columns = ['RANGE','MEAN','MEDIAN','STD']
        f.rename_stat_columns(_demstat_table, _stat_columns, 'DEM_')

        _demstat_df = f.table_to_data_frame(_demstat_table)
    
        # merge into the master dataframe
        _classstat_df = pd.merge(_classstat_df, _demstat_df, on=ZONE_FIELD.lower())

    

    # Save the zonal statistics to a table
    _zonestat_out_filename = _yield_data['name'] + "_zone_stat.csv"
    _stat_files.append(_zonestat_out_filename)
    _out_zonestat_filepath = os.path.join(_mapparam['root'], _zonestat_out_filename)
    f.tweet("MSG: Saving Zonal Statistics\n  -> {0}".format(_out_zonestat_filepath), ap=arcpy)
    _classstat_df.to_csv(_out_zonestat_filepath, index=False)


    # join the results back into the zone layer
    arcpy.JoinField_management(_yield_layer, ZONE_FIELD, _classstat_table, ZONE_FIELD)
    if(_toolparam['dem_raster']):
        arcpy.JoinField_management(_yield_layer, ZONE_FIELD, _demstat_table, ZONE_FIELD)

    _mapparam['maps'].addDataFromPath(_yield_layer)

    # do some hosuecleaning 
    f.deleteGeodatabaseTables(_mapparam['scratch'], table_list=_stat_files)

    f.tweet("MSG: Afinalizado..")
