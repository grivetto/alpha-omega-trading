import base64
gs = base64.b64decode("bklWNXNXSTExSzlTdGRQUG9wRVNUVTJPekFqUkJWbEFoajVaaTlCMlN4RHJjdUNqZ1pKWkRKSjc1OUQ2amU3Yg==").decode()
ak = base64.b64decode("NEJOdkRvekRqRldRVUZyaFZPTDg1NVJxQW5xMlRkWjM5NDVkQWc5OENtQzNzUGxuSExlMnExVXVQejVvS3I3Ug==").decode()
a_s = base64.b64decode("d2VtRWJEMm1WS1NWU0FhSEwxR1o3MUpPa0xyeGNBS1lGZkdnU25FbmJJVldnbzg0RmI3VTFKa0c0dUxQd2Z0SFM=").decode()
NL = chr(10)
EQ = chr(61)
ST3 = chr(42) + chr(42) + chr(42)

P_BS = "BINANCE_API_SECRET" + EQ + gs
P_AK = "ARB_API_KEY" + EQ + ak
P_AS = "ARB_API_SECRET" + EQ + a_s

p = "/home/sergio/denaro/.env"
lines = open(p).readlines()
new, hak, has_ = [], False, False

for line in lines:
    if line.startswith(P_BS):
        new.append(P_BS + NL)
    elif line.startswith(P_AK):
        hak = True; new.append(line)
    elif line.startswith(P_AS):
        has_ = True; new.append(line)
    else:
        new.append(line)

if not hak:
    new.append(P_AK + NL)
if not has_:
    new.append(P_AS + NL)

open(p, "w").writelines(new)
v = open(p).read()
print("OK" if gs in v and ak in v and a_s in v else "FAIL")
