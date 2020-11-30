from django.shortcuts import render

import requests
import os, json
from rest_framework import mixins
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework import permissions
from rest_framework.authentication import TokenAuthentication
from rest_framework.response import Response
from rest_framework.permissions import BasePermission, IsAuthenticated, IsAuthenticatedOrReadOnly, SAFE_METHODS
import datetime
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
import jwt
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from gcs_operations.models import Transaction, FlightPermission
from .models import DigitalSkyLog
from gcs_operations.models import FlightOperation
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.x509 import load_pem_x509_certificate
from cryptography.hazmat.backends import default_backend
from base64 import b64encode, b64decode
from registry.models import Aircraft

from pki_framework.utils import requires_scopes, BearerAuth
from .serializers import DigitalSkyLogSerializer

from gcs_operations.serializers import FlightPermissionSerializer

# Create your views here.



@method_decorator(requires_scopes(['aerobridge.write']), name='dispatch')
class RegisterDrone(mixins.CreateModelMixin, generics.GenericAPIView):

    """
    Execute Drone registration

    """
    serializer_class = DigitalSkyLogSerializer
    def post(self, request, drone_id,format=None):		

        drone = get_object_or_404(Aircraft, pk=drone_id)
        t = Transaction(drone = Aircraft, prefix="registration")
        t.save()

        private_key = os.environ.get('PRIVATE_KEY')
        certificate = os.environ.get('X509_CERTIFICATE')
        private_key = private_key.replace('-----BEGIN ENCRYPTED PRIVATE KEY-----goo', '')
        private_key = private_key.replace('-----END ENCRYPTED PRIVATE KEY-----', '')

    
        priv_key = serialization.load_pem_private_key(private_key, password=None, backend=default_backend())
        
        drone_details ={"droneTypeId": drone.type_id, "version": drone.version, "txn":t.get_txn_id(), "deviceID":drone.device_id, "deviceModelId": drone.device_model_id, "operatorBusinessIdentifier": drone.operator_business_id}
        drone_details_string = json.dumps(drone_details)
        drone_details_bytes = drone_details_string.encode("utf-8") 


        signature = priv_key.sign(drone_details_bytes,padding.PSS(mgf=padding.MGF1(hashes.SHA256()),salt_length=padding.PSS.MAX_LENGTH),hashes.SHA256())
        # Sign the drone details
        signature = b64encode(signature)
        
        securl = os.environ.get('DIGITAL_SKY_URL')
        headers = {'content-type': 'application/json'}

        drone_details ={"droneTypeId": drone.type_id, "version": drone.version, "txn":t.get_txn_id(), "deviceID":drone.device_id, "deviceModelId": drone.device_model_id, "operatorBusinessIdentifier": drone.operator_business_id}


        payload = {"drone": json.dumps(drone_details), "signature":signature, "digitalCertificate":certificate}

        r = requests.post(securl, data= json.dumps(payload), headers=headers)
        now = datetime.datetime.now()
        registration_response = json.loads(r.text)
        if r.status_code == 201:
            # create a entry 
            ds_log = DigitalSkyLog(txn = t, response = r.text, response_code = registration_response['code'], timestamp = now)
            ds_log.save()
            drone.is_registered = True
            drone.save()
            return Response(status=status.HTTP_201_CREATED)
        else:
            ds_log = DigitalSkyLog(txn = t, response = r.text, response_code = registration_response['code'], timestamp = now)
            ds_log.save()
            return Response(status=status.HTTP_400_BAD_REQUEST)


@method_decorator(requires_scopes(['aerobridge.read']), name='dispatch')
class FlyDronePermissionApplicationList(mixins.ListModelMixin, generics.GenericAPIView):
    
    queryset = FlightPermission.objects.all()
    serializer_class = FlightPermissionSerializer

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)
    

@method_decorator(requires_scopes(['aerobridge.write']), name='dispatch')
class FlyDronePermissionApplicationDetail(mixins.CreateModelMixin, generics.GenericAPIView):
    
    queryset = FlightPermission.objects.all()
    serializer_class = FlightPermissionSerializer

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)
    
    def post(self, request, operation_id,format=None):	
        operation = get_object_or_404(FlightOperation, pk=operation_id)

        t = Transaction(drone = Aircraft, prefix="permission")
        t.save()
        permission = FlightPermission(operation= operation)
        permission.save()
        
        flight_plan = operation.flight_plan
        drone = operation.drone_details
        
        payload = {"pilotBusinessIdentifier":drone.operator_business_id,"flyArea":flight_plan.details,"droneId":str(drone.id),"payloadWeightInKg":drone.max_certified_takeoff_weight *1.0, "payloadDetails":"test","flightPurpose":operation.purpose,"typeOfOperation":operation.type_of_operation,"flightTerminationOrReturnHomeCapability":operation.flight_termination_or_return_home_capability,"geoFencingCapability":operation.geo_fencing_capability,"detectAndAvoidCapability":operation.detect_and_avoid_capability,"selfDeclaration":"true","startDateTime":flight_plan.start_datetime,"endDateTime":flight_plan.end_datetime,"recurringTimeExpression":operation.recurring_time_expression,"recurringTimeDurationInMinutes":operation.recurring_time_duration,"recurringTimeExpressionType":"CRON_QUARTZ"}
        
        headers = {'content-type': 'application/json'}

        securl = os.environ.get('DIGITAL_SKY_URL')
        r = requests.post(securl, data= json.dumps(payload), headers=headers)

        now = datetime.datetime.now()
        permission_response = json.loads(r.text)

        if r.status_code == 200:
            if permission_response['status'] == 'APPROVED':
                permission.is_successful = True
            ds_log = DigitalSkyLog(txn = t, response = r.text, response_code = permission_response['code'], timestamp = now)
        else:
            ds_log = DigitalSkyLog(txn = t, response = r.text, response_code = permission_response['code'], timestamp = now)
            ds_log.save()
            return Response(status=status.HTTP_400_BAD_REQUEST)


@method_decorator(requires_scopes(['aerobridge.write']), name='dispatch')
class FlyDronePermissionApplicationFlightLog(mixins.CreateModelMixin, generics.GenericAPIView):
    
    queryset = FlightPermission.objects.all()
    serializer_class = FlightPermissionSerializer

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

@method_decorator(requires_scopes(['aerobridge.write']), name='dispatch')
class DownloadFlyDronePermissionArtefact(mixins.ListModelMixin, generics.GenericAPIView):

    queryset = FlightPermission.objects.all()
    serializer_class = FlightPermissionSerializer

    def get(self, request, permission_id, format=None):
        permission = get_object_or_404(FlightPermission, pk=permission_id)
        
            
        try:
            assert permission.is_successful
        except AssertionError as ae: 
            message ={"status":0, "message":"No permission for operation, please get permission first"}
            return Response(json.dumps(message), status=status.HTTP_400_BAD_REQUEST)
        
        if permission.artefact != "": 
            return Response(permission.artefact, status=status.HTTP_200_OK)
        else:
            # there is no permission artefact 
            # download and save it. 
            
            headers = {'content-type': 'application/json'}
            securl = os.environ.get('DIGITAL_SKY_URL')+ '/api/applicationForm/flyDronePermissionApplication/'+str(permission.id)+'/document/permissionArtifact'
            auth = BearerAuth(os.environ.get('BEARER_TOKEN', ""))
            r = requests.get(securl,auth = auth,  headers=headers)
            now = datetime.datetime.now()
            
            if r.status_code == 200:
            
                ds_log = DigitalSkyLog(txn = t, response = r.text, response_code = permission_response['code'], timestamp = now)
                permission.arefact = r.text()
                permission.save()
                msg = {"status":1, "aretefact": r.text()}
                return Response(json.dumps(msg), status=status.HTTP_200_OK)
            else:
                ds_log = DigitalSkyLog(txn = t, response = r.text, response_code = permission_response['code'], timestamp = now)
                ds_log.save()
                return Response(status=status.HTTP_400_BAD_REQUEST)


    # Process and submit 

