# pip install fastf1
import fastf1
import matplotlib.pyplot as plt
import os

# Create cache folder for FastF1 data
os.makedirs('f1_cache', exist_ok=True)
fastf1.Cache.enable_cache('f1_cache')


class LapData:
    def __init__(self, lap_number, time, is_safety_car=False, pit_stop=False):
        self.lap_number = lap_number
        self.time = time
        self.is_safety_car = is_safety_car
        self.pit_stop = pit_stop

    def __repr__(self):
        return f"<Lap {self.lap_number}: {self.time}s, SC={self.is_safety_car}, PIT={self.pit_stop}>"


class Driver:
    def __init__(self, name, team):
        self.name = name
        self.team = team
        self.laps = []

    def add_lap(self, lap_data):
        self.laps.append(lap_data)

    def get_average_lap_time(self, before_lap=None, after_lap=None):
        filtered = [
            lap.time for lap in self.laps
            if (before_lap is None or lap.lap_number < before_lap) and
            (after_lap is None or lap.lap_number > after_lap) and
            not lap.is_safety_car
        ]
        if not filtered:
            return None
        return sum(filtered) / len(filtered)

    def lap_delta_sc(self, sc_lap, window=3):
        before = [
            lap.time for lap in self.laps
            if sc_lap - window <= lap.lap_number < sc_lap and not lap.is_safety_car
        ]
        after = [
            lap.time for lap in self.laps
            if sc_lap < lap.lap_number <= sc_lap + window and not lap.is_safety_car
        ]
        if before and after:
            avg_before = sum(before) / len(before)
            avg_after = sum(after) / len(after)
            return avg_after - avg_before
        return None

    def __repr__(self):
        return f"<Driver {self.name} ({self.team})>"


class Race:
    def __init__(self, track_name, total_laps):
        self.track_name = track_name
        self.total_laps = total_laps
        self.drivers = []

    def add_driver(self, driver):
        self.drivers.append(driver)

    def get_safety_car_laps(self):
        sc_laps = set()
        for driver in self.drivers:
            for lap in driver.laps:
                if lap.is_safety_car:
                    sc_laps.add(lap.lap_number)
        return sorted(list(sc_laps))

    def __repr__(self):
        return f"<Race at {self.track_name}, {self.total_laps} laps>"


if __name__ == "__main__":
    session = fastf1.get_session(2023, 'Silverstone', 'R')
    session.load()

    race = Race("Silverstone", session.total_laps)

    # STEP 1: Get safety car windows
    sc_messages = session.race_control_messages
    sc_messages = sc_messages[sc_messages['Message'].str.contains("SAFETY CAR", case=False, na=False)]
    print("Race Control Messages related to SC:\n", sc_messages[['Message', 'Time']])

    # Estimate windows (assumes alternating deploy/withdraw)
    sc_times = sc_messages['Time'].tolist()
    sc_windows = []
    for i in range(0, len(sc_times) - 1, 2):
        sc_windows.append((sc_times[i], sc_times[i + 1]))

    print("\nEstimated Safety Car Windows:")
    for start, end in sc_windows:
        print(f"From {start} to {end}")

    # STEP 2: Analyze drivers
    for driver_code in ['HAM', 'VER']:
        laps = session.laps.pick_driver(driver_code).pick_quicklaps()
        driver_info = session.get_driver(driver_code)
        driver = Driver(driver_info['FullName'], driver_info['TeamName'])

        for _, lap in laps.iterlaps():
            lap_number = int(lap['LapNumber'])
            lap_time = lap['LapTime'].total_seconds() if lap['LapTime'] else None
            lap_start_time = lap['StartTime']

            # Check if lap is in any SC window
            is_sc = any(start <= lap_start_time <= end for (start, end) in sc_windows)

            if lap_time is not None:
                driver.add_lap(LapData(lap_number, lap_time, is_safety_car=is_sc))

        race.add_driver(driver)

    print("\n", race)
    sc_laps = race.get_safety_car_laps()
    print("Safety Car Laps (by lap number):", sc_laps)

    # STEP 3: Compute lap time delta around SC
    print("\nLap Time Delta Around Safety Car:")
    for driver in race.drivers:
        print(f"\nDriver: {driver.name}")
        for sc_lap in sc_laps:
            delta = driver.lap_delta_sc(sc_lap, window=3)
            if delta is not None:
                sign = "+" if delta > 0 else "-"
                print(f"  SC Lap {sc_lap}: Δ = {sign}{abs(delta):.2f} sec (Post - Pre)")
            else:
                print(f"  SC Lap {sc_lap}: Not enough data")
