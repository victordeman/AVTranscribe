import React, { useState } from 'react';
import axios from 'axios';

interface AuthProps {
  onLoginSuccess: () => void;
}

const Auth: React.FC<AuthProps> = ({ onLoginSuccess }) => {
  const [isLogin, setIsLogin] = useState(true);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setMessage(null);

    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);

    try {
      if (isLogin) {
        const response = await axios.post('/login', formData);
        if (response.data && response.data.access_token) {
          localStorage.setItem('token', response.data.access_token);
          onLoginSuccess();
        } else {
          setError('Invalid server response: missing access token');
        }
      } else {
        await axios.post('/signup', formData);
        setMessage('Account created! Please login.');
        setIsLogin(true);
      }
    } catch (err: any) { // eslint-disable-line @typescript-eslint/no-explicit-any
      setError(err.response?.data?.detail || 'Authentication failed');
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-lg overflow-hidden p-8 border border-gray-200 mb-8">
      <div className="flex border-b border-gray-100 mb-6">
        <button
          className={`py-2 px-4 font-semibold ${isLogin ? 'text-indigo-700 border-b-2 border-indigo-700' : 'text-gray-500 hover:text-indigo-600'}`}
          onClick={() => setIsLogin(true)}
        >
          Login
        </button>
        <button
          className={`py-2 px-4 font-semibold ${!isLogin ? 'text-indigo-700 border-b-2 border-indigo-700' : 'text-gray-500 hover:text-indigo-600'}`}
          onClick={() => setIsLogin(false)}
        >
          Sign Up
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="username" className="block text-sm font-medium text-gray-700">Username</label>
          <input
            id="username"
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            className="block w-full mt-1 rounded-md border-gray-300 shadow-sm border p-2"
          />
        </div>
        <div>
          <label htmlFor="password" className="block text-sm font-medium text-gray-700">Password</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="block w-full mt-1 rounded-md border-gray-300 shadow-sm border p-2"
          />
        </div>
        <button
          type="submit"
          className="w-full py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 transition"
        >
          {isLogin ? 'Login' : 'Sign Up'}
        </button>
      </form>
      {error && <div className="mt-4 text-red-600 text-sm">{error}</div>}
      {message && <div className="mt-4 text-green-600 text-sm">{message}</div>}
    </div>
  );
};

export default Auth;
