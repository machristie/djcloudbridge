import urllib

from cloudbridge.cloud.interfaces.resources import TrafficDirection
from rest_auth.serializers import UserDetailsSerializer
from rest_framework import serializers
from rest_framework.reverse import reverse

from . import models
from . import view_helpers
from .drf_helpers import CustomHyperlinkedIdentityField
from .drf_helpers import PlacementZonePKRelatedField
from .drf_helpers import ProviderPKRelatedField


class ZoneSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()


class RegionSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    url = CustomHyperlinkedIdentityField(
        view_name='djcloudbridge:region-detail',
        lookup_field='id',
        lookup_url_kwarg='pk',
        parent_url_kwargs=['cloud_pk'])
    name = serializers.CharField()
    zones = CustomHyperlinkedIdentityField(view_name='zone-list',
                                           lookup_field='id',
                                           lookup_url_kwarg='region_pk',
                                           parent_url_kwargs=['cloud_pk'])


class MachineImageSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    url = CustomHyperlinkedIdentityField(view_name='machine_image-detail',
                                         lookup_field='id',
                                         lookup_url_kwarg='pk',
                                         parent_url_kwargs=['cloud_pk'])
    name = serializers.CharField()
    description = serializers.CharField()


class KeyPairSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    url = CustomHyperlinkedIdentityField(view_name='keypair-detail',
                                         lookup_field='id',
                                         lookup_url_kwarg='pk',
                                         parent_url_kwargs=['cloud_pk'])
    name = serializers.CharField()
    material = serializers.CharField(read_only=True)

    def create(self, validated_data):
        provider = view_helpers.get_cloud_provider(self.context.get('view'))
        return provider.security.key_pairs.create(validated_data.get('name'))


class VMFirewallRuleSerializer(serializers.Serializer):
    protocol = serializers.CharField(allow_blank=True)
    from_port = serializers.CharField(allow_blank=True)
    to_port = serializers.CharField(allow_blank=True)
    cidr = serializers.CharField(label="CIDR", allow_blank=True)
    firewall = ProviderPKRelatedField(label="VM Firewall",
                                      queryset='security.vm_firewalls',
                                      display_fields=['name', 'id'],
                                      display_format="{0} (ID: {1})",
                                      required=False,
                                      allow_null=True)
    url = CustomHyperlinkedIdentityField(view_name='vm_firewall_rule-detail',
                                         lookup_field='id',
                                         lookup_url_kwarg='pk',
                                         parent_url_kwargs=['cloud_pk',
                                                            'vm_firewall_pk'])

    def validate(self, data):
        """Cursory data check."""
        if data.get('protocol').lower() not in ['tcp', 'udp', 'icmp']:
            raise serializers.ValidationError(
                'Protocol must be one of: tcp, udp, icmp.')
        try:
            if not (1 < int(data['from_port']) <= 65535):
                raise serializers.ValidationError(
                    'From port must be an integer between 1 and 65535.')
            elif not (1 < int(data['to_port']) <= 65535):
                raise serializers.ValidationError(
                    'To port must be an integer between 1 and 65535.')
        except ValueError:
            raise serializers.ValidationError(
                'To/from ports must be integers.')
        return data

    def create(self, validated_data):
        view = self.context.get('view')
        provider = view_helpers.get_cloud_provider(view)
        vmf_pk = view.kwargs.get('vm_firewall_pk')
        if vmf_pk:
            vmf = provider.security.vm_firewalls.get(vmf_pk)
            if vmf and validated_data.get('firewall'):
                return vmf.rules.create(
                    TrafficDirection.INBOUND,
                    validated_data.get('protocol'),
                    int(validated_data.get('from_port')),
                    int(validated_data.get('to_port')),
                    src_dest_fw=validated_data.get('firewall'))
            elif vmf:
                return vmf.rules.create(TrafficDirection.INBOUND,
                                        validated_data.get('protocol'),
                                        int(validated_data.get('from_port')),
                                        int(validated_data.get('to_port')),
                                        validated_data.get('cidr'))
        return None


class VMFirewallSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    url = CustomHyperlinkedIdentityField(view_name='vm_firewall-detail',
                                         lookup_field='id',
                                         lookup_url_kwarg='pk',
                                         parent_url_kwargs=['cloud_pk'])
    name = serializers.CharField()
    # Technically, the description is required but when wanting to reuse an
    # existing VM firewall with a different resource (eg, creating an
    # instance), we need to be able to call this serializer w/o it.
    description = serializers.CharField(required=False)
    network_id = ProviderPKRelatedField(queryset='networking.networks',
                                        display_fields=['id', 'name'],
                                        display_format="{1} ({0})")
    rules = CustomHyperlinkedIdentityField(view_name='vm_firewall_rule-list',
                                           lookup_field='id',
                                           lookup_url_kwarg='vm_firewall_pk',
                                           parent_url_kwargs=['cloud_pk'])

    def create(self, validated_data):
        provider = view_helpers.get_cloud_provider(self.context.get('view'))
        return provider.security.vm_firewalls.create(
            validated_data.get('name'), validated_data.get('description'),
            validated_data.get('network_id').id)


class NetworkSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    url = CustomHyperlinkedIdentityField(view_name='network-detail',
                                         lookup_field='id',
                                         lookup_url_kwarg='pk',
                                         parent_url_kwargs=['cloud_pk'])
    name = serializers.CharField()
    state = serializers.CharField(read_only=True)
    cidr_block = serializers.CharField(read_only=True)
    subnets = CustomHyperlinkedIdentityField(view_name='subnet-list',
                                             lookup_field='id',
                                             lookup_url_kwarg='network_pk',
                                             parent_url_kwargs=['cloud_pk'])

    def create(self, validated_data):
        provider = view_helpers.get_cloud_provider(self.context.get('view'))
        return provider.network.create(name=validated_data.get('name'))

    def update(self, instance, validated_data):
        try:
            if instance.name != validated_data.get('name'):
                instance.name = validated_data.get('name')
            return instance
        except Exception as e:
            raise serializers.ValidationError("{0}".format(e))


class SubnetSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    url = CustomHyperlinkedIdentityField(view_name='subnet-detail',
                                         lookup_field='id',
                                         lookup_url_kwarg='pk',
                                         parent_url_kwargs=['cloud_pk',
                                                            'network_pk'])
    name = serializers.CharField(allow_blank=True)
    cidr_block = serializers.CharField()
    network_id = serializers.CharField(read_only=True)

    def create(self, validated_data):
        provider = view_helpers.get_cloud_provider(self.context.get('view'))
        net_id = self.context.get('view').kwargs.get('network_pk')
        return provider.network.subnets.create(
            net_id, validated_data.get('cidr_block'),
            name=validated_data.get('name'))


class SubnetSerializerUpdate(SubnetSerializer):
    cidr_block = serializers.CharField(read_only=True)

    def update(self, instance, validated_data):
        try:
            if instance.name != validated_data.get('name'):
                instance.name = validated_data.get('name')
            return instance
        except Exception as e:
            raise serializers.ValidationError("{0}".format(e))


class StaticIPSerializer(serializers.Serializer):
    ip = serializers.CharField(read_only=True)


class VMTypeSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    url = CustomHyperlinkedIdentityField(view_name='vm_type-detail',
                                         lookup_field='pk',
                                         parent_url_kwargs=['cloud_pk'])
    name = serializers.CharField()
    family = serializers.CharField()
    vcpus = serializers.CharField()
    ram = serializers.CharField()
    size_root_disk = serializers.CharField()
    size_ephemeral_disks = serializers.CharField()
    num_ephemeral_disks = serializers.CharField()
    size_total_disk = serializers.CharField()
    extra_data = serializers.DictField(serializers.CharField())


class AttachmentInfoSerializer(serializers.Serializer):
    device = serializers.CharField(read_only=True)
    instance_id = ProviderPKRelatedField(label="Instance ID",
                                         queryset='compute.instances',
                                         display_fields=[
                                             'name', 'id'],
                                         display_format="{0} (ID: {1})",
                                         required=False,
                                         allow_null=True)

    instance = CustomHyperlinkedIdentityField(view_name='instance-detail',
                                              lookup_field='instance_id',
                                              lookup_url_kwarg='pk',
                                              parent_url_kwargs=['cloud_pk'])


class VolumeSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    url = CustomHyperlinkedIdentityField(view_name='volume-detail',
                                         lookup_field='id',
                                         lookup_url_kwarg='pk',
                                         parent_url_kwargs=['cloud_pk'])
    name = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    size = serializers.IntegerField(min_value=0)
    create_time = serializers.CharField(read_only=True)
    zone_id = PlacementZonePKRelatedField(label="Zone",
                                          queryset='non_empty_value',
                                          display_fields=[
                                              'id'],
                                          display_format="{0}",
                                          required=True)
    state = serializers.CharField(read_only=True)
    snapshot_id = ProviderPKRelatedField(label="Snapshot ID",
                                         queryset='storage.snapshots',
                                         display_fields=[
                                             'name', 'id', 'size'],
                                         display_format="{0} (ID: {1},"
                                         " Size: {2} GB)",
                                         write_only=True,
                                         required=False,
                                         allow_null=True)

    attachments = AttachmentInfoSerializer()

    def create(self, validated_data):
        provider = view_helpers.get_cloud_provider(self.context.get('view'))
        try:
            return provider.storage.volumes.create(
                validated_data.get('name'),
                validated_data.get('size'),
                validated_data.get('zone_id'),
                description=validated_data.get('description'),
                snapshot=validated_data.get('snapshot_id'))
        except Exception as e:
            raise serializers.ValidationError("{0}".format(e))

    def update(self, instance, validated_data):
        try:
            if instance.name != validated_data.get('name'):
                instance.name = validated_data.get('name')
            if instance.description != validated_data.get('description'):
                instance.description = validated_data.get('description')
            return instance
        except Exception as e:
            raise serializers.ValidationError("{0}".format(e))


class SnapshotSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    url = CustomHyperlinkedIdentityField(view_name='snapshot-detail',
                                         lookup_field='id',
                                         lookup_url_kwarg='pk',
                                         parent_url_kwargs=['cloud_pk'])
    name = serializers.CharField()
    description = serializers.CharField()
    state = serializers.CharField(read_only=True)
    volume_id = ProviderPKRelatedField(label="Volume ID",
                                       queryset='storage.volumes',
                                       display_fields=[
                                             'name', 'id', 'size'],
                                       display_format="{0} (ID: {1},"
                                       " Size: {2} GB)",
                                       required=True)
    create_time = serializers.CharField(read_only=True)
    size = serializers.IntegerField(min_value=0, read_only=True)

    def create(self, validated_data):
        provider = view_helpers.get_cloud_provider(self.context.get('view'))
        try:
            return provider.storage.snapshots.create(
                validated_data.get('name'),
                validated_data.get('volume_id'),
                description=validated_data.get('description'))
        except Exception as e:
            raise serializers.ValidationError("{0}".format(e))

    def update(self, instance, validated_data):
        try:
            if instance.name != validated_data.get('name'):
                instance.name = validated_data.get('name')
            if instance.description != validated_data.get('description'):
                instance.description = validated_data.get('description')
            return instance
        except Exception as e:
            raise serializers.ValidationError("{0}".format(e))


class InstanceSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    url = CustomHyperlinkedIdentityField(view_name='instance-detail',
                                         lookup_field='id',
                                         lookup_url_kwarg='pk',
                                         parent_url_kwargs=['cloud_pk'])
    name = serializers.CharField()
    public_ips = serializers.ListField(serializers.IPAddressField())
    private_ips = serializers.ListField(serializers.IPAddressField())
    vm_type_id = ProviderPKRelatedField(label="Instance Type",
                                        queryset='compute.vm_types',
                                        display_fields=[
                                            'name'],
                                        display_format="{0}",
                                        required=True)
    vm_type_url = CustomHyperlinkedIdentityField(
        view_name='vm_type-detail',
        lookup_field='vm_type_id',
        lookup_url_kwarg='pk',
        parent_url_kwargs=['cloud_pk'])
    image_id = ProviderPKRelatedField(label="Image",
                                      queryset='compute.images',
                                      display_fields=[
                                               'name', 'id'],
                                      display_format="{0} ({1})",
                                      required=True)
    image_id_url = CustomHyperlinkedIdentityField(
        view_name='machine_image-detail',
        lookup_field='image_id',
        lookup_url_kwarg='pk',
        parent_url_kwargs=['cloud_pk'])
    key_pair_name = ProviderPKRelatedField(label="Keypair Name",
                                           queryset='security.key_pairs',
                                           display_fields=[
                                               'id'],
                                           display_format="{0}",
                                           required=True)
    zone_id = PlacementZonePKRelatedField(label="Placement Zone",
                                          queryset='non_empty_value',
                                          display_fields=[
                                              'id'],
                                          display_format="{0}",
                                          required=True)
    vm_firewall_ids = ProviderPKRelatedField(label="VM Firewalls",
                                             queryset='security.vm_firewalls',
                                             display_fields=['name'],
                                             display_format="{0}",
                                             many=True)
    user_data = serializers.CharField(write_only=True,
                                      style={'base_template': 'textarea.html'})

    def create(self, validated_data):
        provider = view_helpers.get_cloud_provider(self.context.get('view'))
        name = validated_data.get('name')
        image_id = validated_data.get('image_id')
        vm_type = validated_data.get('vm_type_id')
        kp_name = validated_data.get('key_pair_name')
        zone_id = validated_data.get('zone_id')
        vm_firewall_ids = validated_data.get('vm_firewall_ids')
        user_data = validated_data.get('user_data')
        try:
            return provider.compute.instances.create(
                name, image_id, vm_type, zone=zone_id,
                key_pair=kp_name, vm_firewalls=vm_firewall_ids,
                user_data=user_data)
        except Exception as e:
            raise serializers.ValidationError("{0}".format(e))

    def update(self, instance, validated_data):
        try:
            if instance.name != validated_data.get('name'):
                instance.name = validated_data.get('name')
            return instance
        except Exception as e:
            raise serializers.ValidationError("{0}".format(e))


class BucketSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    url = CustomHyperlinkedIdentityField(view_name='bucket-detail',
                                         lookup_field='id',
                                         lookup_url_kwarg='pk',
                                         parent_url_kwargs=['cloud_pk'])
    name = serializers.CharField()
    objects = CustomHyperlinkedIdentityField(view_name='bucketobject-list',
                                             lookup_field='id',
                                             lookup_url_kwarg='bucket_pk',
                                             parent_url_kwargs=['cloud_pk'])

    def create(self, validated_data):
        provider = view_helpers.get_cloud_provider(self.context.get('view'))
        try:
            return provider.storage.buckets.create(validated_data.get('name'))
        except Exception as e:
            raise serializers.ValidationError("{0}".format(e))


class BucketObjectSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    name = serializers.CharField(allow_blank=True)
    size = serializers.IntegerField(read_only=True)
    last_modified = serializers.CharField(read_only=True)
    url = CustomHyperlinkedIdentityField(
        view_name='bucketobject-detail',
        lookup_field='id',
        lookup_url_kwarg='pk',
        parent_url_kwargs=['cloud_pk', 'bucket_pk'])
    download_url = serializers.SerializerMethodField()
    upload_content = serializers.FileField(write_only=True)

    def get_download_url(self, obj):
        """Create a URL for accessing a single instance."""
        kwargs = self.context['view'].kwargs.copy()
        kwargs.update({'pk': obj.id})
        obj_url = reverse('bucketobject-detail',
                          kwargs=kwargs,
                          request=self.context['request'])
        return urllib.parse.urljoin(obj_url, '?format=binary')

    def create(self, validated_data):
        provider = view_helpers.get_cloud_provider(self.context.get('view'))
        bucket_id = self.context.get('view').kwargs.get('bucket_pk')
        bucket = provider.storage.buckets.get(bucket_id)
        try:
            name = validated_data.get('name')
            content = validated_data.get('upload_content')
            if name:
                obj = bucket.objects.create(name)
            else:
                obj = bucket.objects.create(content.name)
            if content:
                obj.upload(content.file.getvalue())
            return obj
        except Exception as e:
            raise serializers.ValidationError("{0}".format(e))

    def update(self, instance, validated_data):
        try:
            instance.upload(
                validated_data.get('upload_content').file.getvalue())
            return instance
        except Exception as e:
            raise serializers.ValidationError("{0}".format(e))


class CloudSerializer(serializers.ModelSerializer):
    slug = serializers.CharField(read_only=True)
    compute = CustomHyperlinkedIdentityField(
        view_name='djcloudbridge:compute-list',
        lookup_field='slug',
        lookup_url_kwarg='cloud_pk')
    security = CustomHyperlinkedIdentityField(view_name='security-list',
                                              lookup_field='slug',
                                              lookup_url_kwarg='cloud_pk')
    storage = CustomHyperlinkedIdentityField(view_name='storage-list',
                                             lookup_field='slug',
                                             lookup_url_kwarg='cloud_pk')
    networks = CustomHyperlinkedIdentityField(view_name='network-list',
                                              lookup_field='slug',
                                              lookup_url_kwarg='cloud_pk')
    static_ips = CustomHyperlinkedIdentityField(view_name='static_ip-list',
                                                lookup_field='slug',
                                                lookup_url_kwarg='cloud_pk')
    cloudman = CustomHyperlinkedIdentityField(view_name='cloudman-list',
                                              lookup_field='slug',
                                              lookup_url_kwarg='cloud_pk')
    region_name = serializers.SerializerMethodField()

    cloud_type = serializers.SerializerMethodField()
    extra_data = serializers.SerializerMethodField()

    def get_region_name(self, obj):
        if hasattr(obj, 'aws'):
            return obj.aws.compute.ec2_region_name
        elif hasattr(obj, 'openstack'):
            return obj.openstack.region_name
        elif hasattr(obj, 'azure'):
            return obj.azure.region_name
        elif hasattr(obj, 'gce'):
            return obj.gce.region_name
        else:
            return "Cloud provider not recognized"

    def get_cloud_type(self, obj):
        if hasattr(obj, 'aws'):
            return 'aws'
        elif hasattr(obj, 'openstack'):
            return 'openstack'
        elif hasattr(obj, 'azure'):
            return 'azure'
        elif hasattr(obj, 'gce'):
            return 'gce'
        else:
            return 'unknown'

    def get_extra_data(self, obj):
        if hasattr(obj, 'aws'):
            aws = obj.aws
            extra_data = {}
            if aws.compute:
                compute = aws.compute
                extra_data['ec2_region_name'] = compute.ec2_region_name
                extra_data['ec2_region_endpoint'] = compute.ec2_region_endpoint
                extra_data['ec2_conn_path'] = compute.ec2_conn_path
                extra_data['ec2_port'] = compute.ec2_port
                extra_data['ec2_is_secure'] = compute.ec2_is_secure
            if aws.object_store:
                s3 = aws.object_store
                extra_data['s3_host'] = s3.s3_host
                extra_data['s3_conn_path'] = s3.s3_conn_path
                extra_data['s3_port'] = s3.s3_port
                extra_data['s3_is_secure'] = s3.s3_is_secure
            return extra_data
        elif hasattr(obj, 'openstack'):
            os = obj.openstack
            return {'auth_url': os.auth_url,
                    'region_name': os.region_name,
                    'identity_api_version': os.identity_api_version
                    }
        elif hasattr(obj, 'azure'):
            azure = obj.azure
            return {'region_name': azure.region_name,
                    'resource_group': azure.resource_group,
                    'storage_account': azure.storage_account,
                    'vm_default_user_name': azure.vm_default_user_name
                    }
        elif hasattr(obj, 'gce'):
            gce = obj.gce
            return {'region_name': gce.region_name,
                    'zone_name': gce.zone_name
                    }
        else:
            return {}

    class Meta:
        model = models.Cloud
        exclude = ('kind',)


class ComputeSerializer(serializers.Serializer):
    instances = CustomHyperlinkedIdentityField(view_name='instance-list',
                                               parent_url_kwargs=['cloud_pk'])
    machine_images = CustomHyperlinkedIdentityField(
        view_name='machine_image-list',
        parent_url_kwargs=['cloud_pk'])
    regions = CustomHyperlinkedIdentityField(view_name='region-list',
                                             parent_url_kwargs=['cloud_pk'])
    vm_types = CustomHyperlinkedIdentityField(view_name='vm_type-list',
                                              parent_url_kwargs=['cloud_pk'])


class SecuritySerializer(serializers.Serializer):
    keypairs = CustomHyperlinkedIdentityField(view_name='keypair-list',
                                              parent_url_kwargs=['cloud_pk'])
    vm_firewalls = CustomHyperlinkedIdentityField(
        view_name='vm_firewall-list',
        parent_url_kwargs=['cloud_pk'])


class StorageSerializer(serializers.Serializer):
    volumes = CustomHyperlinkedIdentityField(view_name='volume-list',
                                             parent_url_kwargs=['cloud_pk'])
    snapshots = CustomHyperlinkedIdentityField(view_name='snapshot-list',
                                               parent_url_kwargs=['cloud_pk'])
    buckets = CustomHyperlinkedIdentityField(view_name='bucket-list',
                                             parent_url_kwargs=['cloud_pk'])


"""
User Profile and Credentials related serializers
"""


class CredentialsSerializer(serializers.Serializer):
    aws = CustomHyperlinkedIdentityField(view_name='awscredentials-list')
    openstack = CustomHyperlinkedIdentityField(
        view_name='openstackcredentials-list')
    azure = CustomHyperlinkedIdentityField(
        view_name='azurecredentials-list')
    gce = CustomHyperlinkedIdentityField(
        view_name='gcecredentials-list')


class AWSCredsSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.IntegerField(read_only=True)
    secret_key = serializers.CharField(
        style={'input_type': 'password'},
        write_only=True,
        required=False
    )
    cloud_id = serializers.CharField(write_only=True)
    cloud = CloudSerializer(read_only=True)

    class Meta:
        model = models.AWSCredentials
        exclude = ('secret_key', 'user_profile')


class OpenstackCredsSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.IntegerField(read_only=True)
    password = serializers.CharField(
        style={'input_type': 'password'},
        write_only=True,
        required=False
    )
    cloud_id = serializers.CharField(write_only=True)
    cloud = CloudSerializer(read_only=True)

    class Meta:
        model = models.OpenStackCredentials
        exclude = ('password', 'user_profile')


class AzureCredsSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.IntegerField(read_only=True)
    secret = serializers.CharField(
        style={'input_type': 'password'},
        write_only=True,
        required=False
    )
    cloud_id = serializers.CharField(write_only=True)
    cloud = CloudSerializer(read_only=True)

    class Meta:
        model = models.AzureCredentials
        exclude = ('secret', 'user_profile')


class GCECredsSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.IntegerField(read_only=True)
    credentials = serializers.CharField(
        write_only=True,
        style={'base_template': 'textarea.html', 'rows': 20},
    )
    cloud_id = serializers.CharField(write_only=True)
    cloud = CloudSerializer(read_only=True)

    class Meta:
        model = models.GCECredentials
        exclude = ('user_profile',)


class CloudConnectionAuthSerializer(serializers.Serializer):
    aws_creds = AWSCredsSerializer(write_only=True, required=False)
    openstack_creds = OpenstackCredsSerializer(write_only=True, required=False)
    azure_creds = AzureCredsSerializer(write_only=True, required=False)
    gce_creds = GCECredsSerializer(write_only=True, required=False)
    result = serializers.CharField(read_only=True)
    details = serializers.CharField(read_only=True)

    def create(self, validated_data):
        provider = view_helpers.get_cloud_provider(self.context.get('view'))
        try:
            provider.authenticate()
            return {'result': 'SUCCESS'}
        except Exception as e:
            return {'result': 'FAILURE', 'details': str(e)}


class UserSerializer(UserDetailsSerializer):
    credentials = CustomHyperlinkedIdentityField(
        view_name='credentialsroute-list', lookup_field=None)
    aws_creds = serializers.SerializerMethodField()
    openstack_creds = serializers.SerializerMethodField()
    azure_creds = serializers.SerializerMethodField()
    gce_creds = serializers.SerializerMethodField()

    def get_aws_creds(self, obj):
        """
        Include a URL for listing this bucket's contents
        """
        try:
            creds = obj.userprofile.credentials.filter(
                awscredentials__isnull=False).select_subclasses()
            return AWSCredsSerializer(instance=creds, many=True,
                                      context=self.context).data
        except models.UserProfile.DoesNotExist:
            return ""

    def get_openstack_creds(self, obj):
        """
        Include a URL for listing this bucket's contents
        """
        try:
            creds = obj.userprofile.credentials.filter(
                openstackcredentials__isnull=False).select_subclasses()
            return OpenstackCredsSerializer(instance=creds, many=True,
                                            context=self.context).data
        except models.UserProfile.DoesNotExist:
            return ""

    def get_azure_creds(self, obj):
        """
        Include a URL for listing this bucket's contents
        """
        try:
            creds = obj.userprofile.credentials.filter(
                azurecredentials__isnull=False).select_subclasses()
            return AzureCredsSerializer(instance=creds, many=True,
                                        context=self.context).data
        except models.UserProfile.DoesNotExist:
            return ""

    def get_gce_creds(self, obj):
        """
        Include a URL for listing this bucket's contents
        """
        try:
            creds = obj.userprofile.credentials.filter(
                gcecredentials__isnull=False).select_subclasses()
            return GCECredsSerializer(instance=creds, many=True,
                                      context=self.context).data
        except models.UserProfile.DoesNotExist:
            return ""

    class Meta(UserDetailsSerializer.Meta):
        fields = UserDetailsSerializer.Meta.fields + \
            ('aws_creds', 'openstack_creds', 'azure_creds', 'gce_creds',
             'credentials')
