"""Exact venue identities whose published street addresses resolve city-only listings.

These are query inputs, never invented coordinates. The normal bounded geocoder
must still verify a physical point. Keep publisher links beside each address.
"""
VENUE_ADDRESSES = {
    'komunitné centrum oáza, stará tržnica': ('Námestie SNP 25, Bratislava', 'https://staratrznica.sk/sk/oaza-booking-info'),
    'veľké koncertné štúdio slov. rozhlasu': ('Mýtna 1, Bratislava', 'https://sosr.stvr.sk/sk/kontakt'),
    'divadlo janart, junácka 10 bratislava': ('Junácka 10, Bratislava', 'https://janartdivadlo.sk/kontakt'),
    'tipos aréna - zimný štadión ondreja nepelu': ('Odbojárov 9, Bratislava', 'https://bratislava.sk/vzdelavanie-a-volny-cas/starz/prevadzky-sportoviska/zimny-stadion-ondreja-nepelu'),
    'dk ružinov - veľká sála': ('Ružinovská 28, Bratislava', 'https://www.cultusruzinov.sk/o-nas'),
    'kultúrne centrum lamač': ('Malokarpatské námestie 3, Bratislava', 'https://www.lamac.sk/potrebujem-vybavit/majetkovopravne-situacie/kratkodoby-prenajom-priestorov'),
    'a4 – priestor súčasnej kultúry': ('Karpatská 2, Bratislava', 'https://www.a4.sk/docs/A4_ponuka%20priestorov%20na%20prenajom.pdf'),
    'dk zrkadlový háj': ('Rovniankova 3, Bratislava', 'https://kulturavpetrzalke.sk/zariadenie/78'),
    'veľká sála, dk zrkadlový háj, bratislava': ('Rovniankova 3, Bratislava', 'https://kulturavpetrzalke.sk/zariadenie/78'),
    'sud - slovenský umelecký dvor, bratislava': ('Ovsištské námestie 1, Bratislava', 'https://slovenskyumeleckydvor.sk/kontakt/'),
}

# The municipal calendar can advertise partner performances outside Bratislava.
# Publisher ownership alone is not proof of the performance's location.
VENUE_LOCALITIES = {
    'rosenfeldov palác': ('Žilina', 'https://rosenfeldovpalac.sk/kontakt/'),
}
