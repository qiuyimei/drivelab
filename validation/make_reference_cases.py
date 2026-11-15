"""Independent analytic fixtures. Does NOT import the DriveLab implementation.

These are derived/synthetic reference values, not measurements or validation of
any physical vehicle. Polynomial coefficients are obtained by solving the six
boundary conditions rather than copying the application's smoothstep formula.
"""
from pathlib import Path
import json
import math
import numpy as np

ROOT = Path(__file__).resolve().parent
G = 9.81
BASE = {"name":"独立解析参考", "scenario":"urban", "speed":100, "leadSpeed":0,
        "distance":1000, "decel":5, "reaction":0.8, "mu":0.8, "radius":250,
        "mass":1800, "wheelbase":2.8, "steeringRatio":15, "steeringLimit":540,
        "brakeLimit":8, "brakeGain":200, "lateralLimit":3, "duration":60,
        "laneWidth":3.5, "laneTime":5}
cases = []

def brake_case(speed, reaction, mu, request, suffix=""):
    cfg = {**BASE, "name":f"解析停车 {speed}/{reaction}/{mu}/{request}{suffix}",
           "speed":speed, "reaction":reaction, "mu":mu, "decel":request}
    v0 = speed/3.6
    a = min(request, cfg["brakeLimit"], mu*G)
    stop_t = reaction + v0/a
    stop_s = v0*reaction + v0*v0/(2*a)
    sample_ts = sorted(set([0., .1, max(0.,math.floor(reaction*10)/10),
                            math.ceil(reaction*10)/10, 2.,5.,
                            math.floor(stop_t*10)/10,math.ceil(stop_t*10)/10,60.]))
    samples = []
    for t in sample_ts:
        if t < reaction:
            velocity, x = v0, v0*t
        elif t < stop_t:
            tau=t-reaction
            velocity, x = v0-a*tau, v0*reaction+v0*tau-a*tau*tau/2
        else:
            velocity, x = 0., stop_s
        samples.append({"time":t,"speed":velocity*3.6,"distance":x})
    cases.append({"id":f"brake-{len(cases)+1:03d}","kind":"closed_form_stopping",
                  "source_ids":["ENG-001"],"config":cfg,
                  "expected":{"effectiveDecel":a,"stoppingDistance":stop_s,"stopTime":stop_t},
                  "samples":samples,"absolute_tolerance":1e-8})

for speed in [30,60,100,120]:
    for reaction in [0,.8,1.5]:
        for mu in [.2,.55,.8]:
            for request in [2,5,9]:
                brake_case(speed,reaction,mu,request)
brake_case(100,.83,.8,5," 非整步响应")

for speed in [36,72,108]:
    for radius in [50,100,250]:
        v=speed/3.6
        cfg={**BASE,"name":f"解析圆周 {speed}/{radius}","scenario":"curve",
             "speed":speed,"radius":radius,"duration":20}
        cases.append({"id":f"curve-{speed}-{radius}","kind":"radius_first_geometry",
                      "source_ids":["ENG-002","ENG-003"],"config":cfg,
                      "expected":{"maxLat":v*v/radius,
                                  "yaw":v/radius*180/math.pi,
                                  "steering":math.atan(cfg["wheelbase"]/radius)*180/math.pi*cfg["steeringRatio"]},
                      "absolute_tolerance":1e-8})

def polynomial_derivative(coeff,t,order):
    total=0.
    for degree in range(order,6):
        factor=math.factorial(degree)/math.factorial(degree-order)
        total += coeff[degree]*factor*t**(degree-order)
    return total

for width in [2.,3.5,5.]:
    for duration in [2.,3.5,5.,8.]:
        # Solve p(0)=0,p'(0)=0,p''(0)=0,p(T)=W,p'(T)=0,p''(T)=0.
        mat=[]
        rhs=[]
        for t,order,value in [(0.,0,0.),(0.,1,0.),(0.,2,0.),
                              (duration,0,width),(duration,1,0.),(duration,2,0.)]:
            mat.append([0. if degree<order else
                        math.factorial(degree)/math.factorial(degree-order)*t**(degree-order)
                        for degree in range(6)])
            rhs.append(value)
        coeff=np.linalg.solve(np.array(mat),np.array(rhs))
        cfg={**BASE,"name":f"边界条件求解换道 {width}/{duration}","scenario":"lane",
             "speed":90,"laneWidth":width,"laneTime":duration,"duration":20}
        samples=[]
        for n in range(201):
            t=n/10
            tau=max(0.,min(duration,t-cfg["reaction"]))
            y=polynomial_derivative(coeff,tau,0)
            lateral=polynomial_derivative(coeff,tau,2) if cfg["reaction"]<=t<=cfg["reaction"]+duration else 0.
            samples.append({"time":t,"y":y,"lateral":lateral})
        cases.append({"id":f"quintic-{width}-{duration}","kind":"six_boundary_linear_solve",
                      "source_ids":["ENG-004"],"config":cfg,
                      "coefficients_ascending":coeff.tolist(),
                      "expected":{"exactContinuousPeakLateral":10*math.sqrt(3)/3*width/duration**2},
                      "samples":samples,"absolute_tolerance":1e-7,
                      "peak_note":"连续峰值不必恰好落在 0.1 秒采样点；测试应检查采样值，不应要求采样峰值与连续极值逐位相等。"})

payload={"title":"独立解析基准集合", "classification":"independent_analytic_reference",
         "not_real_vehicle_measurements":True, "does_not_import_application":True,
         "purpose":"验证公式实现、单位、数值积分与给定轨迹边界条件；不证明实车精度、真实安全性或超限后的动态响应。",
         "generator":"make_reference_cases.py", "cases":cases,
         "counts":{"braking":109,"steady_curve":9,"quintic_boundary_solve":12,"total":len(cases)}}
(ROOT/"independent-reference-cases.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(payload["counts"]))
