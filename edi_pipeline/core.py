"""Strict single-interchange, single-group, single-transaction demo profile."""
from datetime import datetime
from decimal import Decimal, InvalidOperation

class ValidationError(ValueError):
    pass

def require(condition, message):
    if not condition:
        raise ValidationError(message)

def parse(text):
    text = text.lstrip('\ufeff\r\n ')
    require(len(text) >= 106 and text.startswith('ISA'), 'ISA: missing fixed-width header')
    element, component, terminator = text[3], text[104], text[105]
    require(len({element, component, terminator}) == 3, 'ISA: delimiters must differ')
    header = text[:105].split(element)
    widths = [2,10,2,10,2,15,2,15,6,4,1,5,9,1,1,1]
    require(len(header) == 17 and [len(v) for v in header[1:]] == widths,
            'ISA: invalid fixed-width fields')
    segments = [s.strip().split(element) for s in text.split(terminator) if s.strip()]
    tags = [s[0] for s in segments]
    for tag in ['ISA','GS','ST','SE','GE','IEA']:
        require(tags.count(tag) == 1, f'{tag}: exactly one required by demo profile')
    require(tags[0:3] == ['ISA','GS','ST'] and tags[-3:] == ['SE','GE','IEA'],
            'Envelope: invalid nesting/order')
    def one(tag, minimum):
        seg = segments[tags.index(tag)]
        require(len(seg) > minimum, f'{tag}: insufficient elements')
        return seg
    isa, gs, st, se, ge, iea = (one(t,n) for t,n in [('ISA',16),('GS',8),('ST',2),('SE',2),('GE',2),('IEA',2)])
    require(isa[12] == '00401' and gs[8] == '004010', 'Version: only 004010 supported')
    require(isa[15] == 'T', 'ISA15: only test interchanges accepted')
    require(isa[13].isdigit() and len(isa[13]) == 9, 'ISA13: nine digits required')
    require(isa[13] == iea[2] and gs[6] == ge[2] and st[2] == se[2], 'Envelope: control number mismatch')
    require(ge[1] == '1' and iea[1] == '1', 'Envelope: group/transaction counts must be one')
    require(se[1].isdigit() and int(se[1]) == len(segments)-4, 'SE01: segment count mismatch')
    kind = st[1]
    require(kind in {'204','210','214'}, 'ST01: unsupported transaction')
    require(gs[1] == {'204':'SM','210':'IM','214':'QM'}[kind], 'GS01: functional identifier mismatch')
    required = {'204':{'B2','B2A','S5','N1'}, '210':{'B3','C3','L3'}, '214':{'B10','LX','AT7'}}[kind]
    require(required <= set(tags), 'Business: missing required segments: '+','.join(sorted(required-set(tags))))
    def field(tag, index):
        s = one(tag,index)
        require(bool(s[index].strip()), f'{tag}{index:02}: value required')
        return s[index].strip()
    result = {'transaction_type':kind, 'control_number':st[2], 'interchange_control':isa[13],
              'sender':isa[6].strip(), 'receiver':isa[8].strip(), 'version':gs[8]}
    if kind == '204':
        result.update(shipment_id=field('B2',4), carrier_scac=field('B2',2),
                      payment_method=field('B2',6),
                      stops=[{'sequence':s[1], 'reason':s[2]} for s in segments if s[0]=='S5' and len(s)>2])
        require(bool(result['stops']), 'S5: a complete stop required')
    elif kind == '210':
        try:
            raw = field('B3',7)
            require(raw.isdigit(), 'B307: nonnegative integer cents required')
            amount = Decimal(raw)/100
        except InvalidOperation as exc:
            raise ValidationError('B307: invalid amount') from exc
        date = field('B3',6)
        try:
            datetime.strptime(date, '%Y%m%d')
        except ValueError as exc:
            raise ValidationError('B306: invalid invoice date') from exc
        require(field('L3',5) == raw, 'L305: total must match B307')
        result.update(invoice_id=field('B3',2), shipment_id=field('B3',3),
                      invoice_date=date, amount=str(amount.quantize(Decimal('0.01'))),
                      currency=field('C3',1), carrier_scac=field('B3',11))
    else:
        code, date, time = field('AT7',1), field('AT7',5), field('AT7',6)
        require(code in {'X1','X3','X6','AF','D1'}, 'AT701: unsupported demo status')
        try:
            datetime.strptime(date+time, '%Y%m%d%H%M')
        except ValueError as exc:
            raise ValidationError('AT7: invalid event date/time') from exc
        result.update(shipment_id=field('B10',1), bill_of_lading=field('B10',2),
                      carrier_scac=field('B10',3), status_code=code,
                      status={'X1':'arrived_delivery','X3':'arrived_pickup','X6':'in_transit','AF':'departed_pickup','D1':'delivered'}[code],
                      event_date=date, event_time=time, time_code=field('AT7',7))
    return result
