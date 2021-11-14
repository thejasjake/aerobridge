from django.db.models.query_utils import select_related_descend
from rest_framework import serializers
from .models import Transaction, FlightOperation, FlightPlan, FlightLog, FlightPermission, CloudFile, SignedFlightLog
from registry.models import Firmware
import tempfile
import fiona
import geopandas as gpd
import json
import arrow
from fastkml import kml
gpd.io.file.fiona.drvsupport.supported_drivers['KML'] = 'rw'

class FirmwareSerializer(serializers.ModelSerializer):
    ''' A serializer for saving Firmware ''' 
    class Meta: 
        model = Firmware
        fields = '__all__'
        ordering = ['-created_at']
        
class FlightPlanListSerializer(serializers.ModelSerializer):
    ''' A serializer for Flight Operations '''
    def validate(self, data):
        """
        Check flight plan is valid KML        
        """
        try:
            k = kml.KML()            
            k.from_string(data['kml'])
            
        except Exception as ve:
            raise serializers.ValidationError("Not a valid KML, please enter a valid KML object")            
        
        return data

    def create(self, validated_data):
        kml = validated_data['kml']
        f =  fiona.BytesCollection(bytes(kml, encoding='utf-8'))
        df = gpd.GeoDataFrame()

        # iterate over layers
        for layer in fiona.listlayers(f.path):
            s = gpd.read_file(f.path, driver='KML', layer=layer)
            df = df.append(s, ignore_index=True)
            
        validated_data['geo_json'] = json.loads(df.to_json())
        print(type(df.to_json()))
        return super(FlightPlanListSerializer, self).create(validated_data)
    class Meta:
        model = FlightPlan	
        exclude = ('is_editable',)
        read_only_fields = ('geo_json',)
        ordering = ['-created_at']

class FlightPlanSerializer(serializers.ModelSerializer):

    def validate(self, data):
        """
        Check flight plan is valid KML        
        """
        try:
            k = kml.KML()            
            k.from_string(data['kml'])
            data['kml'] = k.to_string()
        except Exception as ve:
            raise serializers.ValidationError("Not a valid KML, please enter a valid KML object")            
        
        return data

    def create(self, validated_data):
        kml = validated_data['kml']
        tmp = tempfile.NamedTemporaryFile()
        with open(tmp.name, 'w') as f:
                f.write(kml) # where `stuff` is, y'know... stuff to write (a string)
    
        geo_json = kml2geojson.main.convert(tmp)
        print(geo_json)
        return super(FlightPlanSerializer, self).create(validated_data)
    class Meta:
        model = FlightPlan		
        exclude = ('is_editable',)
        read_only_fields = ('geo_json',)
        ordering = ['-created_at']

class FlightOperationListSerializer(serializers.ModelSerializer):
    ''' A serializer for Flight Operations '''
    def validate(self, data):
        """
        Check flight plan is  valid KML        
        """
        s_date = data.get("start_datetime")
        e_date = data.get("end_datetime")
        start_date = arrow.get(s_date)
        end_date = arrow.get(e_date)
        if end_date < start_date:
            raise serializers.ValidationError("End date should be greater than start date.")

    class Meta:
        model = FlightOperation	
        fields = '__all__'
        ordering = ['-created_at']

     
class FlightOperationSerializer(serializers.ModelSerializer):
    ''' A serializer for Flight Operations '''
    # drone = AircraftDetailSerializer(read_only=True)
    # flight_plan = FlightPlanSerializer(read_only=True)
    class Meta:
        model = FlightOperation	
        exclude = ('is_editable',)
        ordering = ['-created_at']
        
class FlightPermissionSerializer(serializers.ModelSerializer):
    operation = FlightOperationSerializer(read_only=True)
    class Meta:
        model = FlightPermission	
        fields = '__all__'	
        ordering = ['-created_at']
        
        
class FlightOperationPermissionSerializer(serializers.ModelSerializer):
    ''' A serializer for Flight Operations '''
    permission = serializers.SerializerMethodField()
    
    def get_permission(self, obj):
        permission = FlightPermission.objects.get(operation_id = obj.id)
        return permission.json
    class Meta:
        model = FlightOperation	
        fields = ('operation_id', 'permission')
        ordering = ['-created_at']
    
# class TransactionSerializer(serializers.ModelSerializer):
#     ''' A serializer to the transaction view '''

#     class Meta:
#         model = Transaction		
#         fields = '__all__'
#         ordering = ['-created_at']
        
class FlightLogSerializer(serializers.ModelSerializer):
    ''' A serializer for Flight Logs '''
    def validate(self, data):
        """
        Check flight log already exists for the operation  """
        raw_log = data.get("raw_log")
        try: 
            json.loads(raw_log)
        except TypeError as te:
            raise serializers.ValidationError("A raw flight log must be a valid JSON object")        
        return data

    class Meta:
        model = FlightLog	
        exclude = ('is_submitted','is_editable',)
        ordering = ['-created_at']
 
class SignedFlightLogSerializer(serializers.ModelSerializer):
    ''' A serializer for Signed Flight Logs '''
    class Meta:
        model = SignedFlightLog	        
        ordering = ['-created_at']
        fields = '__all__'


class CloudFileSerializer(serializers.ModelSerializer):
    ''' A serializer for Cloud Files '''
    class Meta:
        model = CloudFile
        fields = '__all__'
        ordering = ['-created_at']