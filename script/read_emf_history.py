#!/usr/bin/env python3
import asyncio
import json
import datetime
import sys
import aiohttp
from pathlib import Path

sys.path.append(str((Path(__file__).parent.parent.resolve())))
print(sys.path)

from pymultimatic.api import Connector, ApiError, urls
from pymultimatic.model import mapper

device_ids = {
    "Wärmepumpe": "NoneGateway-LL_HMU03_0351_HP_Platform_Outdoor_Monobloc_PR_EBUS",
    "Hydraulikstation": "NoneGateway-LL_VWZ02_0351_HP_Platform_Indoor_Monobloc_PR_EBUS",
}
functions = {
    "Heizung": "CENTRAL_HEATING",
    "Warmwasser": "DHW",
}
energy_types = {
    "Stromverbrauch": "CONSUMED_ELECTRICAL_POWER",
    "Umweltenergie": "ENVIRONMENTAL_YIELD"
}

async def read_data(user: str, passw: str, first_day, time_range, device_id: str, function: str, energy_type: str, fname: str):

    end_date = datetime.date.today()
    begin_date = datetime.date.fromisoformat(first_day)

    outf = open(Path("output") / fname, "wt", encoding="utf-8")

    print(f"// Retrieving EMF data for {device_id=} function={function}\n// {time_range=} {begin_date=} {end_date=} ...")
    print('// Trying to connect with user ' + user)

    async with aiohttp.ClientSession() as sess:
        connector = Connector(user, passw, sess)

        try:
            await connector.login(True)
            print('// Login successful')
        except ApiError as err:
            print(err.message)
            print(err.response)
            print(err.status)

        facilities = await connector.get(urls.facilities_list())
        serial = mapper.map_serial_number(facilities)

        url_method = getattr(urls, "emf_report_device")

        next_date = begin_date

        print("[", file = outf)
        first = True
        try:
            while next_date <= end_date:
                url = url_method(energy_type = energy_type,
                                function = function,
                                time_range = time_range,
                                start = next_date.isoformat(),
                                offset = "0",
                                **{'serial': serial,
                                    'device_id': device_id,
                                    })
                if first:
                    first = False
                else:
                    print(",", file = outf)
                # print(f"// {url}", file=outf)

                print(json.dumps(await connector.get(url)), file=outf)

                if time_range == "DAY":
                    next_date += datetime.timedelta(days=1)
                elif time_range == "WEEK":
                    next_date += datetime.timedelta(days=7)
                elif time_range == "MONTH":
                    raise NotImplementedError("addMonth")
                elif time_range == "YEAR":
                    raise NotImplementedError("addYear")
                print(f"{next_date=}") 
                await asyncio.sleep(5)
            print("]", file = outf)

        except ApiError as err:
            print(err.message)
            print(err.response)
            print(err.status)


async def main(user: str, passw: str, first_day: str, time_range: str):
    for device_name, device_id in device_ids.items():
        for function_name, function_id in functions.items():
            for energy_name, energy_type in energy_types.items():
                if device_name == "Hydraulikstation" and energy_name == "Umweltenergie":
                    continue # Beim Innengerät gibt es keine Umweltenergie
                fname = f"{device_name}-{function_name}-{energy_name}-{first_day}-{time_range.lower()}.json"
                await read_data(user, passw, first_day, time_range, device_id, function_id, energy_type, fname)

if __name__ == "__main__":
    if not len(sys.argv) == 5:
        print('Usage: python3 read_emf_history.py user pass first_day time_range')
        sys.exit(0)
    user = sys.argv[1]
    passw = sys.argv[2]
    first_day = sys.argv[3]
    time_range = sys.argv[4].upper()
    assert(time_range in ["DAY", "WEEK", "MONTH, YEAR"])

    asyncio.get_event_loop().run_until_complete(main(user, passw, first_day, time_range))