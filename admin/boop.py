class DisplayHandler:
    def __init__(self, oled):
        self.oled = oled
        self.current_page = 0
        self.total_pages = 3  # Three focused pages with clear information hierarchy
        print("Display handler initialized with user-focused design")

    def draw_readings_page(self, readings, page):
        """Draw sensor readings based on current page"""
        print(f"Drawing readings page {page}")

        # Create blank image for drawing
        image = Image.new("1", (self.oled.width, self.oled.height))
        draw = ImageDraw.Draw(image)

        # Clear display
        draw.rectangle((0, 0, self.oled.width, self.oled.height), outline=0, fill=0)

        # Define fonts
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 10)
        label_font = ImageFont.load_default()
        value_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
        unit_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9)

        if page == 0:  # Air Quality Focus
            # Title
            draw.text((2, 0), "AIR QUALITY", font=title_font, fill=1)
            draw.line((0, 12, self.oled.width, 12), fill=1)

            # Get air quality values
            co2 = readings.get('eco2') or readings.get('ens_eco2')
            tvoc = readings.get('tvoc') or readings.get('ens_tvoc')
            aqi = readings.get('ens_aqi')

            # CO2 - Large and prominent
            if co2:
                draw.text((5, 16), "Carbon Dioxide:", font=label_font, fill=1)
                draw.text((5, 26), str(co2), font=value_font, fill=1)
                draw.text((5 + draw.textlength(str(co2), font=value_font) + 2, 34), "ppm", font=unit_font, fill=1)

                # Add simple quality indicator
                if co2 < 800:
                    quality = "GOOD"
                elif co2 < 1000:
                    quality = "FAIR"
                else:
                    quality = "POOR"
                draw.text((90, 26), quality, font=label_font, fill=1)

            # TVOC - Below CO2
            if tvoc:
                draw.text((5, 48), "VOC Level:", font=label_font, fill=1)
                draw.text((70, 48), f"{tvoc} ppb", font=label_font, fill=1)

            # AQI if available
            if aqi:
                draw.text((5, 58), "Air Quality Index:", font=label_font, fill=1)
                draw.text((100, 58), str(aqi), font=label_font, fill=1)

            print(f"Air Quality - CO2: {co2}, TVOC: {tvoc}, AQI: {aqi}")

        elif page == 1:  # Climate Focus
            # Title
            draw.text((2, 0), "CLIMATE", font=title_font, fill=1)
            draw.line((0, 12, self.oled.width, 12), fill=1)

            # Get climate values
            temp = (readings.get('temperature') or
                   readings.get('aht_temperature') or
                   readings.get('bmp_temperature'))

            humidity = (readings.get('humidity') or
                       readings.get('aht_humidity'))

            # Temperature - Large and prominent
            if temp:
                draw.text((5, 16), "Temperature:", font=label_font, fill=1)
                temp_text = f"{temp:.1f}"
                draw.text((5, 26), temp_text, font=value_font, fill=1)
                draw.text((5 + draw.textlength(temp_text, font=value_font) + 2, 34), "°C", font=unit_font, fill=1)

                # Add comfort indicator
                if 20 <= temp <= 25:
                    comfort = "COMFORTABLE"
                elif 18 <= temp <= 27:
                    comfort = "ACCEPTABLE"
                else:
                    comfort = "UNCOMFORTABLE"
                draw.text((90, 26), comfort[:8], font=label_font, fill=1)
                if len(comfort) > 8:
                    draw.text((90, 36), comfort[8:], font=label_font, fill=1)

            # Humidity - Below temperature
            if humidity:
                draw.text((5, 48), "Humidity:", font=label_font, fill=1)
                hum_text = f"{humidity:.1f}"
                draw.text((60, 48), hum_text, font=label_font, fill=1)
                draw.text((60 + draw.textlength(hum_text, font=label_font) + 2, 48), "%", font=label_font, fill=1)

                # Humidity bar
                draw.rectangle((5, 58, 123, 62), outline=1, fill=0)
                bar_width = int((humidity / 100) * 118)
                draw.rectangle((5, 58, 5 + bar_width, 62), outline=1, fill=1)

            print(f"Climate - Temperature: {temp:.1f if temp else 'N/A'}°C, Humidity: {humidity:.1f if humidity else 'N/A'}%")

        elif page == 2:  # Pressure and Sensors
            # Title
            draw.text((2, 0), "PRESSURE & SENSORS", font=title_font, fill=1)
            draw.line((0, 12, self.oled.width, 12), fill=1)

            # Get pressure and altitude
            pressure = (readings.get('pressure') or
                       readings.get('bmp_pressure'))

            altitude = (readings.get('altitude') or
                       readings.get('bmp_altitude'))

            # Pressure - Large and prominent
            if pressure:
                draw.text((5, 16), "Barometric Pressure:", font=label_font, fill=1)
                pressure_text = f"{pressure/100:.1f}"
                draw.text((5, 26), pressure_text, font=value_font, fill=1)
                draw.text((5 + draw.textlength(pressure_text, font=value_font) + 2, 34), "hPa", font=unit_font, fill=1)

                # Weather tendency
                if 1000 <= pressure/100 <= 1025:
                    tendency = "STABLE"
                elif pressure/100 < 1000:
                    tendency = "STORMY"
                else:
                    tendency = "FAIR"
                draw.text((90, 26), tendency, font=label_font, fill=1)

            # Altitude if available
            if altitude:
                draw.text((5, 48), "Altitude:", font=label_font, fill=1)
                draw.text((60, 48), f"{altitude:.1f} m", font=label_font, fill=1)

            # Active sensors
            sensors_found = []
            if 'eco2' in readings or 'tvoc' in readings:
                sensors_found.append("SGP30")
            if 'temperature' in readings or 'humidity' in readings or 'pressure' in readings:
                sensors_found.append("BME680")
            if 'aht_temperature' in readings or 'aht_humidity' in readings:
                sensors_found.append("AHT21")
            if 'bmp_temperature' in readings or 'bmp_pressure' in readings:
                sensors_found.append("BMP280")
            if 'ens_aqi' in readings or 'ens_tvoc' in readings:
                sensors_found.append("ENS160")

            # Display active sensors
            if sensors_found:
                sensor_text = ", ".join(sensors_found)
                # Wrap text if needed
                if draw.textlength(sensor_text, font=label_font) > 123:
                    words = sensor_text.split(", ")
                    line1 = words[0]
                    line2 = ""
                    for word in words[1:]:
                        if draw.textlength(line1 + ", " + word, font=label_font) <= 123:
                            line1 += ", " + word
                        else:
                            if line2:
                                line2 += ", " + word
                            else:
                                line2 = word
                    draw.text((5, 58), line1, font=label_font, fill=1)
                    if line2:
                        draw.text((5, 58), line2, font=label_font, fill=1)
                else:
                    draw.text((5, 58), sensor_text, font=label_font, fill=1)
            else:
                draw.text((5, 58), "No sensors detected", font=label_font, fill=1)

            print(f"Pressure & Sensors - Pressure: {pressure/100:.1f if pressure else 'N/A'} hPa, " +
                  f"Altitude: {altitude:.1f if altitude else 'N/A'} m, " +
                  f"Active sensors: {', '.join(sensors_found) if sensors_found else 'None'}")

        # Display the image
        self.oled.image(image)
        self.oled.show()
        print(f"Page {page} displayed")

    def draw_canary_state(self, state, readings):
        """Draw the canary with air quality state"""
        print(f"Drawing canary with state: {state}")

        # Create blank image for drawing
        image = Image.new("1", (self.oled.width, self.oled.height))
        draw = ImageDraw.Draw(image)

        # Clear display
        draw.rectangle((0, 0, self.oled.width, self.oled.height), outline=0, fill=0)

        # Define fonts
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
        label_font = ImageFont.load_default()

        # Set title based on state with clear meaning
        if state == "warning":
            title = "POOR AIR QUALITY"
            message = "Open windows or use air purifier"
        elif state == "good":
            title = "EXCELLENT AIR"
            message = "Air quality is optimal"
        elif state == "medium":
            title = "FAIR AIR QUALITY"
            message = "Consider ventilation"
        elif state == "caution":
            title = "DECLINING AIR"
            message = "Monitor and ventilate soon"
        else:
            title = "UNKNOWN STATUS"
            message = "Check sensor readings"

        # Draw title - centered
        title_width = draw.textlength(title, font=title_font)
        title_x = max(2, (self.oled.width - title_width) // 2)
        draw.text((title_x, 2), title, font=title_font, fill=1)

        # Draw the bird
        self.draw_bird(draw, state)

        # Draw message below bird
        message_width = draw.textlength(message, font=label_font)
        message_x = max(2, (self.oled.width - message_width) // 2)
        draw.text((message_x, 45), message, font=label_font, fill=1)

        # Show key readings at bottom
        co2 = readings.get('eco2') or readings.get('ens_eco2')
        tvoc = readings.get('tvoc') or readings.get('ens_tvoc')

        if co2 and tvoc:
            reading_text = f"CO2: {co2} ppm   TVOC: {tvoc} ppb"
            draw.line((0, 55, self.oled.width, 55), fill=1)
            draw.text((2, 57), reading_text, font=label_font, fill=1)

        # Display the image
        self.oled.image(image)
        self.oled.show()
        print(f"Canary state displayed: {title}")