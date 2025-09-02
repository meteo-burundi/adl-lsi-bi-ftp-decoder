from adl_ftp_plugin.registries import ftp_decoder_registry
from django.apps import AppConfig


class LSIBurundiFTPDecoderConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = "adl_lsi_bi_ftp_decoder"
    
    def ready(self):
        from .decoders import LSIBurundiFTPDecoder
        
        ftp_decoder_registry.register(LSIBurundiFTPDecoder())
