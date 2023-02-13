#!/usr/bin/env python3
import asyncio
import json
import datetime
import sys

import aiohttp

sys.path.append("..")

from pymultimatic.api import Connector, ApiError, urls
from pymultimatic.model import mapper


async def main(user, passw, first_day, time_range):

    end_date = datetime.date.today()
    begin_date = datetime.date.fromisoformat(first_day)

    # device_id = "NoneGateway-LL_HMU03_0351_HP_Platform_Outdoor_Monobloc_PR_EBUS"
    device_id = "NoneGateway-LL_VWZ02_0351_HP_Platform_Indoor_Monobloc_PR_EBUS"
    # function = "CENTRAL_HEATING"
    function = "DHW"
    energy_type = "CONSUMED_ELECTRICAL_POWER"
    # energy_type = "ENVIRONMENTAL_YIELD"

    print(f"// Retrieving EMF data for {device_id=} function={function}\n// {time_range=} {begin_date=} {end_date=} ")

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

        print("[")
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
                    print(",")
                print(f"// {url}")
                print(json.dumps(await connector.get(url)))

                if time_range == "DAY":
                    next_date += datetime.timedelta(days=1)
                elif time_range == "WEEK":
                    next_date += datetime.timedelta(days=7)
                elif time_range == "MONTH":
                    raise NotImplementedError("addMonth")
                elif time_range == "YEAR":
                    raise NotImplementedError("addYear")
                
                await asyncio.sleep(2)
            print("]")

        except ApiError as err:
            print(err.message)
            print(err.response)
            print(err.status)


if __name__ == "__main__":
    if not len(sys.argv) == 5:
        print('Usage: python3 read_emf_history.py user pass first_day time_range')
        sys.exit(0)
    user = sys.argv[1]
    passw = sys.argv[2]
    first_day = sys.argv[3]
    time_range = sys.argv[4]
    assert(time_range in ["DAY", "WEEK", "MONTH, YEAR"])

    asyncio.get_event_loop().run_until_complete(main(user, passw, first_day, time_range))