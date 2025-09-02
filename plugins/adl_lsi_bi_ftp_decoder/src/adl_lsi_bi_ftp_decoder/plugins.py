from adl.core.registries import Plugin


class PluginNamePlugin(Plugin):
    type = "adl_lsi_bi_ftp_decoder"
    label = "ADL LSI BI FTP Decoder"
    
    def get_urls(self):
        return []
    
    def get_station_data(self, station_link, start_date=None, end_date=None):
        return []
