from app.database import SessionLocal
from app.models import Gym

TEST_GYMS = [
    ("Test Gym Downtown San Jose", "100 Test St, San Jose, CA", 37.3382, -121.8863),
    ("Test Gym Willow Glen", "200 Test Ave, San Jose, CA", 37.3092, -121.8984),
    ("Test Gym Santana Row", "300 Test Blvd, San Jose, CA", 37.3209, -121.9484),
    ("Test Gym Berryessa", "400 Test Way, San Jose, CA", 37.3688, -121.8680),
    ("Test Gym Campbell", "500 Test Rd, Campbell, CA", 37.2872, -121.9500),
]


def main():
    db = SessionLocal()
    try:
        for name, address, lat, lng in TEST_GYMS:
            exists = db.query(Gym).filter(Gym.name == name).first()
            if not exists:
                db.add(Gym(name=name, address=address, latitude=lat, longitude=lng))
        db.commit()
        print("Seeded test gyms")
    finally:
        db.close()


if __name__ == "__main__":
    main()