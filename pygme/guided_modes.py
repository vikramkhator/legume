import numpy as np
from scipy.optimize import fsolve, bisect
from pygme.utils import RedhefferStar, I_alpha, J_alpha
''' 
Function to compute the guided modes of a multi-layer structure
Input
	g_array  		: numpy array of wave vector amplitudes 
	eps_array		: numpy array of slab permittivities, starting with lower 
					  cladding and ending with upper cladding

	d_array			: thicknesses of each layer
	n_modes			: maximum number of solutions to look for, starting from 
					  the lowest-frequency one
	omega_lb		: lower bound of omega
	omega_ub		: upper bound of omega
	step			: step size for root finding (should be smaller than the 
						minimum expected separation between modes)
	tol 			: tolerance in the omega boundaries for the root finding 
	mode			: polarization, 'te' or 'tm' (maybe change to "pol")
Output
	om_guided   	: array of size n_modes x length(g_array) with the guided 
					  mode frequencies
	coeffs_guided	: A, B coefficients of the modes in every layer
'''


'''
Note: few things that need to be cleared out here 
	- g_array in the functions should just be a single g-value 
	- not clear if the analytic normalization works for more than one layer
	- currenlty this is kinda slow, should be optimized
	- and finally, the code should be cleaned up
'''

def test_mode():
	return 'lol'

def guided_modes(g_array, eps_array, d_array, n_modes=1, 
		omega_lb=None, omega_ub=None, step=1e-3, tol=1e-4, mode='TE'):
	om_guided = []
	coeffs_guided = []
	for g in g_array:
		(omegas, coeffs) = guided_mode_given_g(g=g, eps_array=eps_array, 
			d_array=d_array, n_modes=n_modes, 
			omega_lb=omega_lb, omega_ub=omega_ub, 
			step=step, tol=tol, mode=mode)
		om_guided.append(omegas)
		coeffs_guided.append(coeffs)
	return (om_guided, coeffs_guided)

def guided_mode_given_g(g, eps_array, d_array, n_modes=1, 
	omega_lb=None, omega_ub=None, step=1e-2, tol=1e-2, mode='TE'):
	'''
	Currently, we do 'bisection' in all the regions of interest until n_modes 
	target is met. For alternative variations, see guided_modes_draft.py
	'''
	if omega_lb is None:
		omega_lb = g/np.sqrt(eps_array[1:-1].max())
	if omega_ub is None:
		omega_ub = g/min(eps_array[0],eps_array[-1])
	# print('omega bounds',omega_lb,omega_ub)
	if mode.lower()=='te':
		D22real = lambda x,*args: D22_TE(x,*args).real
		D22imag = lambda x,*args: D22_TE(x,*args).imag
		# D22abs = lambda x,*args: abs(D22_TE(x,*args))
	elif mode.lower()=='tm':
		D22real = lambda x,*args: D22_TM(x,*args).real
		D22imag = lambda x,*args: D22_TM(x,*args).imag
		# D22abs = lambda x,*args: abs(D22_TM(x,*args))
	else:
		raise ValueError("Mode should be 'TE' or 'TM'. What is {} ?".format(mode))
	omega_bounds = np.arange(omega_lb + tol, omega_ub - tol, step)
	# Some special care for when g is close to zero
	if omega_bounds.size < 2:
		omega_bounds = np.linspace(omega_lb+1e-15, omega_ub-1e-15, 2)
	omega_solutions = [] ## solving for D22_real
	chis = []
	coeffs = []
	gs = np.full(eps_array.shape, g)
	# print('num of intervals to search:',len(omega_bounds))
	for i,lb in enumerate(omega_bounds[:-1]):
		if len(omega_solutions) >= n_modes:
			break
		ub=omega_bounds[i+1]
		if D22real(lb,gs,eps_array,d_array)*D22real(ub,gs,eps_array,d_array) < 0:
			omega = bisect(D22real,lb,ub,args=(gs,eps_array,d_array))
			omega_solutions.append(omega)
			chi_array = chi(omega, gs, eps_array)
			if mode.lower()=='te' or mode.lower()=='tm':				
				AB = AB_matrices(omega, gs, eps_array, d_array, 
									chi_array, mode)
				norm = normalization_coeff(omega, gs, eps_array, d_array, 
									AB, mode)

				# norm_num = normalization_num(omega, gs, eps_array, d_array, mode=mode)
				# print(np.abs(norm), np.abs(norm_num))

				coeffs.append(AB / np.sqrt(norm))
			else:
				raise ValueError("Mode should be 'TE' or 'TM'")


			# print('mode in btw',lb,ub, D22real(omega,gs,eps_array,d_array))
			# print(D22real(lb,gs,eps_array,d_array),D22real(ub,gs,eps_array,d_array))
		# except ValueError: ## i.e. no solution in the interval
			# print('no modes in btw',lb,ub)
			# pass

	# print('solution for real',omega_solutions)
	omega_solutions_final = omega_solutions
	### ideally we should pick simultaneous roots to both real and imag parts, but because imag part is too noisy and densely crossing zero, we just take roots to real part
	# omega_solutions_final = []
	# for i in omega_solutions:
	# 	if  D22imag(i,gs,eps_array,d_array)<tol:
	# 		omega_solutions_final.append(i)
	# 	else:
	# 		print('Warning: D22 is not purely real. The numerical routine needs modification. Contact developers.')
			### if this happens, c.f.guided_modes_draft.py and solve for the simultaneous root to D22real and D22imag
	# print('final solution',omega_solutions_final)
	return (omega_solutions_final, coeffs)


def chi(omega, g, eps):
	'''
	Function to compute k_z
	Input
		omega			: frequency * 2π , in units of light speed / unit length
		eps_array		: slab permittivity
		g 				: wave vector along propagation direction (ß_x)
	Output
		k_z
	'''
	return np.sqrt(eps*omega**2 - g**2, dtype=np.complex)

def S_T_matrices_TM(omega, g_array, eps_array, d_array):
	'''
	Function to get a list of S and T matrices for D22 calculation
	'''
	assert len(g_array)==len(eps_array), 'g_array and eps_array should both have length = num_layers+2'
	assert len(d_array)==len(eps_array)-2, 'd_array should have length = num_layers'
	chi_array = chi(omega, g_array, eps_array)
	# print(chi_array)
	S11 = eps_array[1:]*chi_array[:-1] + eps_array[:-1]*chi_array[1:]
	S12 = eps_array[1:]*chi_array[:-1] - eps_array[:-1]*chi_array[1:]
	S22 = S11
	S21 = S12
	S_matrices = 0.5/eps_array[1:].reshape(-1,1,1)/chi_array[:-1].reshape(-1,1,1) * np.array([[S11,S12],[S21,S22]]).transpose([2,0,1]) ## this is how TE differs from TM
	T11 = np.exp(1j*chi_array[1:-1]*d_array)
	T22 = np.exp(-1j*chi_array[1:-1]*d_array)
	T_matrices = np.array([[T11,np.zeros_like(T11)],[np.zeros_like(T11),T22]]).transpose([2,0,1])
	return S_matrices, T_matrices

def D22_TM(omega, g_array, eps_array, d_array):
	'''
	Function to get eigen modes by solving D22=0
	Input
		omega 			: frequency * 2π , in units of light speed / unit length
		g_array			: shape[M+1,1], wave vector along propagation direction (ß_x)
		eps_array		: shape[M+1,1], slab permittivities
		d_array			: thicknesses of each layer
	Output
		abs(D_22) 
	(S matrices describe layers 0...M-1, T matrices describe layers 1...M-1)
	(num_layers = M-1)
	'''
	S_matrices, T_matrices = S_T_matrices_TM(omega, g_array, eps_array, d_array)
	# print('S matrices', S_matrices)
	# print('T matrices', T_matrices)
	D = S_matrices[0,:,:]
	for i,S in enumerate(S_matrices[1:]):
		T = T_matrices[i]
		D = S.dot(T.dot(D))
	return D[1,1]

def S_T_matrices_TE(omega, g_array, eps_array, d_array):
	'''
	Function to get a list of S and T matrices for D22 calculation
	'''
	assert len(g_array)==len(eps_array), 'g_array and eps_array should both have length = num_layers+2'
	assert len(d_array)==len(eps_array)-2, 'd_array should have length = num_layers'
	chi_array = chi(omega, g_array, eps_array)
	# print('chi array',chi_array)
	# print(omega, g_array[1], eps_array[1]*omega**2 - g_array[1]**2)
	S11 = chi_array[:-1] + chi_array[1:]
	S12 = chi_array[:-1] - chi_array[1:]
	S22 = S11
	S21 = S12
	S_matrices = 0.5/chi_array[:-1].reshape(-1,1,1) * np.array([[S11,S12],[S21,S22]]).transpose([2,0,1]) ## this is how TE differs from TM
	T11 = np.exp(1j*chi_array[1:-1]*d_array)
	T22 = np.exp(-1j*chi_array[1:-1]*d_array)
	T_matrices = np.array([[T11,np.zeros_like(T11)],[np.zeros_like(T11),T22]]).transpose([2,0,1])
	return S_matrices, T_matrices

def D22_TE(omega, g_array, eps_array, d_array):
	'''
	Function to get eigen modes by solving D22=0
	Input
		omega 			: frequency * 2π , in units of light speed / unit length
		g_array			: shape[M+1,1], wave vector along propagation direction (ß_x)
		eps_array		: shape[M+1,1], slab permittivities
		d_array			: thicknesses of each layer
	Output
		abs(D_22) 
	(S matrices describe layers 0...M-1, T matrices describe layers 1...M-1)
	(num_layers = M-1)
	'''
	S_matrices, T_matrices = S_T_matrices_TE(omega, g_array, eps_array, d_array)
	# print('S matrices', S_matrices)
	# print('T matrices', T_matrices)
	D = S_matrices[0,:,:]
	# print('S0',D)
	for i,S in enumerate(S_matrices[1:]):
		T = T_matrices[i]
		D = S.dot(T.dot(D))
		# print('S',S)
		# print('T',T)
	# print('D',D)
	return D[1,1]

def TMtoSM(TM):
	'''
	Function to convert 2*2 transfer matrix to corresponding scattering matrix
	'''
	SM = np.array([[-TM[1,0]/TM[1,1],				1.0/TM[1,1]],
				   [TM[0,0]-TM[0,1]*TM[1,0]/TM[1,1],	TM[0,1]/TM[1,1]]])
	return SM

def D22_TE2(omega, g_array, eps_array, d_array):
	'''
	Scattering matrix formalism for D22_TE. Hopefully can be numerically more stable.
	'''
	S_matrices, T_matrices = S_T_matrices_TE(omega, g_array, eps_array, d_array)
	D = TMtoSM(S_matrices[0,:,:])
	for i,S in enumerate(S_matrices[1:]):
		T = T_matrices[i]
		# print(np.linalg.cond(T)) ### roughly 1e30 at max
		# D = RedhefferStar(TMtoSM(S), RedhefferStar(TMtoSM(T),D))
		# print('T\n',T,TMtoSM(T))
		# print('S\n',S,TMtoSM(S))
		# print('red\n',RedhefferStar(TMtoSM(S),TMtoSM(T)))
		# print('D\n',D)
		ST = TMtoSM(S.dot(T))
		# print('ST\n',ST)
		# D = RedhefferStar(ST, D)
		# D = RedhefferStar(RedhefferStar(TMtoSM(S),TMtoSM(T)),D)
		D = RedhefferStar(TMtoSM(S),RedhefferStar(TMtoSM(T),D))
	return 1.0/D[0,1]

def D22_TE3(omega, g_array, eps_array, d_array):
	'''
	Discard small part for D22_TE. Hopefully can be numerically more stable.
	'''
	S_matrices, T_matrices = S_T_matrices_TE(omega, g_array, eps_array, d_array)
	D = S_matrices[0,:,:]
	for i,S in enumerate(S_matrices[1:]):
		T = T_matrices[i]
		if np.linalg.cond(T)>1e20:
			T = np.array([[0,0],[0,1]])
		# D = RedhefferStar(TMtoSM(S), RedhefferStar(TMtoSM(T),D))
		# print('T\n',T,TMtoSM(T))
		# print('S\n',S,TMtoSM(S))
		# print('D\n',D)
		# D = RedhefferStar(ST, D)
		# D = RedhefferStar(RedhefferStar(TMtoSM(S),TMtoSM(T)),D)
		D = S.dot(T.dot(D))
	return D[1,1]

def AB_matrices(omega, g_array, eps_array, d_array, chi_array=None, mode='TE'):
	'''
	Function to calculate A,B coeff
	Output: array of shape [M+1,2]
	'''
	assert len(g_array)==len(eps_array), 'g_array and eps_array should both have length = num_layers+2'
	assert len(d_array)==len(eps_array)-2, 'd_array should have length = num_layers'
	if chi_array is None:
		chi_array = chi(omega, g_array, eps_array)
	# print('len chiarray', len(chi_array))
	# print(chi_array)
	if mode=='TE':
		S_matrices, T_matrices = S_T_matrices_TE(omega, g_array, eps_array, d_array)
	elif mode=='TM':
		S_matrices, T_matrices = S_T_matrices_TM(omega, g_array, eps_array, d_array)
	else:
		raise Exception('Mode should be TE or TM. What is {} ?'.format(mode))
	A0 = 0
	B0 = 1 ### this fixes the normalization for H and E
	AB0 = np.array([A0, B0]).reshape(-1,1)
	ABs = [AB0, S_matrices[0].dot(AB0)] ### A, B coeff for each layer
	for i,S in enumerate(S_matrices[1:]):
		ABs.append(S_matrices[i+1].dot(T_matrices[i].dot(ABs[-1])))
	return np.array(ABs)

def normalization_coeff(omega, g_array, eps_array, d_array, ABref, mode='TE'):
	### here all entries in g_array should be same
	assert len(g_array)==len(eps_array), 'g_array and eps_array should both have length = num_layers+2'
	assert len(d_array)==len(eps_array)-2, 'd_array should have length = num_layers'
	chi_array = chi(omega, g_array, eps_array)
	As = ABref[:,0]
	Bs = ABref[:,1]
	if mode == 'TM': ## ??? if we generalize for complex eps, shall we change square to modulus square?
		term1 = eps_array[0]**2 / np.abs(chi_array[0])**2 * omega**2 / 1 * (Bs[0] * Bs[0].conjugate()) * J_alpha(chi_array[0]-chi_array[0].conjugate())
		term2 = eps_array[-1]**2 / np.abs(chi_array[-1])**2 * omega**2 / 1 * (As[-1] * As[-1].conjugate()) * J_alpha(chi_array[-1]-chi_array[-1].conjugate())
		term3 = eps_array[1:-1]**2 / np.abs(chi_array[1:-1])**2 * omega**2 / 1 * (
				(As[1:-1] * As[1:-1].conjugate()) * I_alpha(chi_array[1:-1]-chi_array[1:-1].conjugate(),d_array) + \
				(Bs[1:-1] * Bs[1:-1].conjugate()) * I_alpha(chi_array[1:-1].conjugate()-chi_array[1:-1],d_array) - \
				(As[1:-1].conjugate() * Bs[1:-1]) * I_alpha(-chi_array[1:-1]-chi_array[1:-1].conjugate(),d_array) - \
				(As[1:-1] * Bs[1:-1].conjugate()) * I_alpha(chi_array[1:-1]+chi_array[1:-1].conjugate(),d_array)
				)
		# print(term3.shape)
		return term1 + term2 + np.sum(term3)
	elif mode == 'TE': ## ??? if we generalize for complex eps, shall we change square to modulus square?
		term1 = (1 + g_array[0]**2 / chi_array[0] / chi_array[0].conjugate()) * (Bs[0] * Bs[0].conjugate()) * J_alpha(chi_array[0]-chi_array[0].conjugate())
		term2 = (1 + g_array[-1]**2 / chi_array[-1] / chi_array[-1].conjugate()) * (As[-1] * As[-1].conjugate()) * J_alpha(chi_array[-1]-chi_array[-1].conjugate())
		term3 = (1 + g_array[1:-1]**2 / chi_array[1:-1] / chi_array[1:-1].conjugate()) * (
				(As[1:-1] * As[1:-1].conjugate()) * I_alpha(chi_array[1:-1]-chi_array[1:-1].conjugate(), d_array) + \
				(Bs[1:-1] * Bs[1:-1].conjugate()) * I_alpha(chi_array[1:-1].conjugate()-chi_array[1:-1], d_array)
				) +\
				(1 - g_array[1:-1]**2 / chi_array[1:-1] / chi_array[1:-1].conjugate()) * (
				(As[1:-1].conjugate() * Bs[1:-1]) * I_alpha(-chi_array[1:-1]-chi_array[1:-1].conjugate(), d_array) + \
				(As[1:-1] * Bs[1:-1].conjugate()) * I_alpha(chi_array[1:-1]+chi_array[1:-1].conjugate(), d_array)
				)
		# print(g_array.shape, d_array.shape)
		# print(term3.shape)
		return term1 + term2 + np.sum(term3)
	else:
		raise Exception('Mode should be TE or TM. What is {} ?'.format(mode))

def phi_by_z(zs, omega, g_array, eps_array, d_array, mode = 'TE'):
	'''
	Function to calculate A,B coeff given z (z=0 for the bottom layer's bottom surface)
	'''
	assert len(g_array)==len(eps_array), 'g_array and eps_array should both have length = num_layers+2'
	assert len(d_array)==len(eps_array)-2, 'd_array should have length = num_layers'
	chi_array = chi(omega, g_array, eps_array)
	print('len chiarray should be l+1', len(chi_array))
	ABref = AB_matrices(omega, g_array, eps_array, d_array, chi_array, mode)
	print('len ABref should be l+1', len(ABref))
	zref = d_array.cumsum() ## z values for each interface, excluding the first one z=0
	zref = np.insert(zref, 0, 0) ## bottom layer's zref
	print('zref',zref)
	print('len zj ref should be l')
	chis = [] ### chi that should be used for each z value
	ABs = [] ### A, B coeff that should be used for each z value
	zjs = [] ### zref value that should be used for each z value i.e. the value for zj for expression (z-zj)
	for z in zs:
		if z<=0:
			chis.append(chi_array[0])
			ABs.append(ABref[0])
			zjs.append(0)
		elif z>=zref[-1]:
				chis.append(chi_array[-1])
				ABs.append(ABref[-1])
				zjs.append(zref[-1])
		else:
			for i,zj in enumerate(zref[1:]):
				if z<=zj:
					chis.append(chi_array[i+1])
					ABs.append(ABref[i+1])
					zjs.append(zref[i])
					break
	ABs = np.array(ABs)
	print('shape ABs should be [l+1,2]',ABs.shape)
	As = ABs[:,0].flatten()
	Bs = ABs[:,1].flatten()
	chis = np.array(chis)
	zjs = np.array(zjs)
	print('len chis should be l+1',len(chis))
	print('zs',zs)
	print('zjs',zjs)
	print('chis',chis)
	print('As,Bs',As,Bs)
	phis = As * np.exp(1j*chis*(zs-zjs)) + Bs * np.exp(-1j*chis*(zs-zjs))
	return phis

def H_by_z(zs, omega, g_array, eps_array, d_array, mode = 'TE'):
	'''
	Function to calculate A,B coeff given z (z=0 for the bottom layer's bottom surface)
	'''
	assert len(g_array)==len(eps_array), 'g_array and eps_array should both have length = num_layers+2'
	assert len(d_array)==len(eps_array)-2, 'd_array should have length = num_layers'
	chi_array = chi(omega, g_array, eps_array)
	# print('len chiarray should be l+1', len(chi_array))
	ABref = AB_matrices(omega, g_array, eps_array, d_array, chi_array, mode)
	# print('len ABref should be l+1', len(ABref))
	zref = d_array.cumsum() ## z values for each interface, excluding the first one z=0
	zref = np.insert(zref, 0, 0) ## bottom layer's zref
	# print('zref',zref)
	# print('len zj ref should be l')
	chis = [] ### chi that should be used for each z value
	ABs = [] ### A, B coeff that should be used for each z value
	zjs = [] ### zref value that should be used for each z value i.e. the value for zj for expression (z-zj)
	epses = [] ### eps value that should be used for each z value 
	for z in zs:
		if z<=0:
			chis.append(chi_array[0])
			ABs.append(ABref[0])
			zjs.append(0)
			epses.append(eps_array[0])
		elif z>=zref[-1]:
				chis.append(chi_array[-1])
				ABs.append(ABref[-1])
				zjs.append(zref[-1])
				epses.append(eps_array[-1])
		else:
			for i,zj in enumerate(zref[1:]):
				if z<=zj:
					chis.append(chi_array[i+1])
					ABs.append(ABref[i+1])
					epses.append(eps_array[i+1])
					zjs.append(zref[i])
					break
	ABs = np.array(ABs)
	# print('shape ABs should be [l+1,2]',ABs.shape)
	As = ABs[:,0].flatten()
	Bs = ABs[:,1].flatten()
	chis = np.array(chis)
	zjs = np.array(zjs)
	# print('len chis should be l+1',len(chis))
	# print('zs',zs)
	# print('zjs',zjs)
	# print('zs-zjs',zs-zjs)
	# print('chis',chis)
	# print('As',As)
	# print('Bs',Bs)
	if mode=='TM':
		Hs = (As * np.exp(1j*chis*(zs-zjs)) - Bs * np.exp(-1j*chis*(zs-zjs))) * epses * omega / chis ### c=1
		# print(np.exp(1j*chis*(zs-zjs)))
		# print(np.exp(-1j*chis*(zs-zjs)))
	else:
		print('not implemented yet')
		return None

	return Hs

def normalization_num(omega, gs, epses, ds, dcladding=3, mode='TM'):
	'''
	Function to calculate int H_conj * H dr from current choice of A,B
	Input:
		dcladding should be large enough for exponential decay into cladding to completely die off
	Return the coeff s.t. if we do A/=np.sqrt(coeff), B/=np.sqrt(coeff), then we can get int H_conj * H dr = 1
	'''
	zs = np.linspace(-dcladding, np.sum(ds)+dcladding, 2000)
	Hs = H_by_z(zs=zs, omega=omega, g_array=gs, eps_array=epses, d_array=ds, mode=mode)
	return np.sum(Hs*Hs.conjugate()*(zs[1]-zs[0]))