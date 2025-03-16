import React, {useState, useEffect, useCallback, useRef} from 'react';
import {Bell, Settings, Trash2, Plus} from 'lucide-react';

const API_BASE_URL = 'http://localhost:8000';

const App = () => {
    const [users, setUsers] = useState([]);
    const [selectedUser, setSelectedUser] = useState(null);
    const [courses, setCourses] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [activeTab, setActiveTab] = useState('courses');
    const [refreshSettings, setRefreshSettings] = useState({
        min_refresh_interval: 30,
        max_refresh_interval: 40
    });

    // Form refs instead of state for input fields
    const userFormRef = useRef(null);
    const courseFormRef = useRef(null);
    const settingsFormRef = useRef(null);

    // Modal states
    const [showAddUserModal, setShowAddUserModal] = useState(false);
    const [showAddCourseModal, setShowAddCourseModal] = useState(false);
    const [showSettingsModal, setShowSettingsModal] = useState(false);

    const fetchUsers = useCallback(async () => {
        setIsLoading(true);
        try {
            const response = await fetch(`${API_BASE_URL}/users/`);
            if (!response.ok) throw new Error('Failed to fetch users');
            const data = await response.json();
            setUsers(data);
        }
        catch (error) {
            console.error('Error fetching users:', error);
        } finally {
            setIsLoading(false);
        }
    }, []);

    const fetchCourses = useCallback(async (userId) => {
        setIsLoading(true);
        try {
            const response = await fetch(`${API_BASE_URL}/users/${userId}/courses`);
            if (!response.ok) throw new Error('Failed to fetch courses');
            const data = await response.json();
            setCourses(data);
        }
        catch (error) {
            console.error('Error fetching courses:', error);
            setCourses([]);
        } finally {
            setIsLoading(false);
        }
    }, []);

    const fetchSettings = useCallback(async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/settings/`);
            if (!response.ok) throw new Error('Failed to fetch settings');
            const data = await response.json();
            setRefreshSettings(data);
        }
        catch (error) {
            console.error('Error fetching settings:', error);
        }
    }, []);

    useEffect(() => {
        fetchUsers();
        fetchSettings();
    }, [fetchUsers, fetchSettings]);

    useEffect(() => {
        if (users.length > 0 && !selectedUser) {
            setSelectedUser(users[0]);
        }
    }, [users, selectedUser]);

    useEffect(() => {
        if (selectedUser) {
            fetchCourses(selectedUser.id);
        }
    }, [selectedUser, fetchCourses]);

    const handleUserSelect = (user) => {
        setSelectedUser(user);
    };

    const handleAddUser = async (e) => {
        e.preventDefault();

        // Get values directly from form elements
        const name = userFormRef.current.elements.name.value;
        const webhookUrl = userFormRef.current.elements.webhook_url.value;

        if (!name || !webhookUrl) {
            alert('Please fill in all fields');
            return;
        }

        try {
            const response = await fetch(`${API_BASE_URL}/users/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({name, webhook_url: webhookUrl}),
            });

            if (!response.ok) throw new Error('Failed to add user');

            const createdUser = await response.json();
            setUsers(prevUsers => [...prevUsers, createdUser]);
            setShowAddUserModal(false);
            setSelectedUser(createdUser);

            // Reset form
            userFormRef.current.reset();
        }
        catch (error) {
            console.error('Error adding user:', error);
            alert('Failed to add user: ' + error.message);
        }
    };

    const handleAddCourse = async (e) => {
        e.preventDefault();

        // Get values directly from form elements
        const courseName = courseFormRef.current.elements.course_name.value;
        const crn = courseFormRef.current.elements.crn.value;
        const professor = courseFormRef.current.elements.professor.value;

        if (!courseName || !crn || !professor) {
            alert('Please fill in all fields');
            return;
        }

        try {
            const response = await fetch(`${API_BASE_URL}/users/${selectedUser.id}/courses`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    course_name: courseName,
                    crn: crn,
                    professor: professor
                }),
            });

            if (!response.ok) throw new Error('Failed to add course');

            const createdCourse = await response.json();
            setCourses([...courses, createdCourse]);
            setShowAddCourseModal(false);

            // Reset form
            courseFormRef.current.reset();
        }
        catch (error) {
            console.error('Error adding course:', error);
            alert('Failed to add course: ' + error.message);
        }
    };

    const handleDeleteCourse = async (courseId) => {
        try {
            const response = await fetch(`${API_BASE_URL}/courses/${courseId}`, {
                method: 'DELETE',
            });

            if (!response.ok) throw new Error('Failed to delete course');

            setCourses(courses.filter(course => course.id !== courseId));
        }
        catch (error) {
            console.error('Error deleting course:', error);
            alert('Failed to delete course: ' + error.message);
        }
    };

    const handleDeleteUser = async (userId) => {
        // Using a custom confirmation dialog approach instead of window.confirm
        if (!window.confirm('Are you sure? This will delete all associated courses.')) {
            return;
        }

        try {
            const response = await fetch(`${API_BASE_URL}/users/${userId}`, {
                method: 'DELETE',
            });

            if (!response.ok) throw new Error('Failed to delete user');

            const updatedUsers = users.filter(user => user.id !== userId);
            setUsers(updatedUsers);

            if (selectedUser && selectedUser.id === userId) {
                if (updatedUsers.length > 0) {
                    setSelectedUser(updatedUsers[0]);
                }
                else {
                    setSelectedUser(null);
                    setCourses([]);
                }
            }
        }
        catch (error) {
            console.error('Error deleting user:', error);
            alert('Failed to delete user: ' + error.message);
        }
    };

    const handleUpdateSettings = async (e) => {
        e.preventDefault();

        // Get values directly from form elements
        const minInterval = parseFloat(settingsFormRef.current.elements.min_interval.value);
        const maxInterval = parseFloat(settingsFormRef.current.elements.max_interval.value);

        const settings = {
            min_refresh_interval: minInterval,
            max_refresh_interval: maxInterval
        };

        try {
            const response = await fetch(`${API_BASE_URL}/settings/`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(settings),
            });

            if (!response.ok) throw new Error('Failed to update settings');

            const updatedSettings = await response.json();
            setRefreshSettings(updatedSettings);
            setShowSettingsModal(false);
            alert('Settings updated successfully!');
        }
        catch (error) {
            console.error('Error updating settings:', error);
            alert('Failed to update settings: ' + error.message);
        }
    };

    // Modal component
    const Modal = ({isOpen, onClose, title, children}) => {
        if (!isOpen) return null;

        return (
            <div className="fixed inset-0 bg-gray-600 bg-opacity-50 flex items-center justify-center p-4 z-50">
                <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
                    <div className="p-4 border-b border-gray-200 flex justify-between items-center">
                        <h3 className="text-lg font-medium">{title}</h3>
                        <button
                            className="text-gray-400 hover:text-gray-500"
                            onClick={onClose}
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24"
                                 stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                      d="M6 18L18 6M6 6l12 12"/>
                            </svg>
                        </button>
                    </div>
                    <div className="p-4">
                        {children}
                    </div>
                </div>
            </div>
        );
    };

    // Render loading state
    if (isLoading && users.length === 0) {
        return (
            <div className="flex justify-center items-center h-screen bg-gray-100">
                <div className="text-center bg-white p-8 rounded-lg shadow-md">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-red-800 mx-auto"></div>
                    <p className="mt-4 text-gray-600">Loading howdyseek...</p>
                    <p className="text-xs text-gray-400 mt-2">howdyseek > all</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-100">
            {/* Header - Texas A&M Maroon */}
            <header className="bg-red-900 shadow">
                <div className="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8 flex justify-between items-center">
                    <div className="flex items-center">
                        <h1 className="text-2xl font-bold text-white">HowdySeek</h1>
                        <span className="ml-4 text-sm text-white">Configuration Portal</span>
                    </div>
                    <div className="flex items-center space-x-4">
                        <button
                            onClick={() => setShowSettingsModal(true)}
                            className="text-white hover:text-gray-200 flex items-center"
                        >
                            <Settings size={20} className="mr-1"/>
                            <span className="text-sm">Settings</span>
                        </button>
                    </div>
                </div>
            </header>

            <main className="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8">
                <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                    {/* Sidebar */}
                    <div className="lg:col-span-1">
                        <div className="bg-white shadow rounded-lg p-4">
                            <div className="flex justify-between items-center mb-4">
                                <h2 className="text-lg font-medium text-gray-900">Users</h2>
                                <button
                                    className="text-sm bg-red-800 hover:bg-red-900 text-white py-1 px-3 rounded flex items-center"
                                    onClick={() => setShowAddUserModal(true)}
                                >
                                    <Plus size={16} className="mr-1"/>
                                    Add
                                </button>
                            </div>

                            <div className="space-y-2">
                                {users.length === 0 ? (
                                    <p className="text-gray-500 text-sm">No users added yet.</p>
                                ) : (
                                    users.map(user => (
                                        <div
                                            key={user.id}
                                            className={`cursor-pointer p-2 rounded flex justify-between items-center ${
                                                selectedUser && selectedUser.id === user.id
                                                    ? 'bg-red-50 border-l-4 border-red-800'
                                                    : 'hover:bg-gray-100'
                                            }`}
                                            onClick={() => handleUserSelect(user)}
                                        >
                                            <div className="truncate">
                                                <p className="font-medium">{user.name}</p>
                                            </div>
                                            <button
                                                className="text-gray-400 hover:text-red-600 ml-2"
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleDeleteUser(user.id);
                                                }}
                                            >
                                                <Trash2 size={16}/>
                                            </button>
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Main content */}
                    <div className="lg:col-span-3">
                        {selectedUser ? (
                            <div className="bg-white shadow rounded-lg overflow-hidden">
                                <div className="p-4 border-b border-gray-200">
                                    <div className="flex justify-between items-center">
                                        <div>
                                            <h2 className="text-lg font-medium text-gray-900">
                                                {selectedUser.name}
                                            </h2>
                                        </div>
                                        <div>
                                            <button
                                                className="text-sm bg-red-800 hover:bg-red-900 text-white py-1 px-3 rounded flex items-center"
                                                onClick={() => setShowAddCourseModal(true)}
                                            >
                                                <Plus size={16} className="mr-1"/>
                                                Add Course
                                            </button>
                                        </div>
                                    </div>
                                </div>

                                <div>
                                    {/* Tab navigation */}
                                    <div className="border-b border-gray-200">
                                        <nav className="-mb-px flex">
                                            <button
                                                className={`${
                                                    activeTab === 'courses'
                                                        ? 'border-red-800 text-red-800'
                                                        : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                                                } w-1/2 py-4 px-1 text-center border-b-2 font-medium text-sm flex justify-center items-center`}
                                                onClick={() => setActiveTab('courses')}
                                            >
                                                <Bell size={16} className="mr-2"/>
                                                Courses
                                            </button>
                                            <button
                                                className={`${
                                                    activeTab === 'settings'
                                                        ? 'border-red-800 text-red-800'
                                                        : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                                                } w-1/2 py-4 px-1 text-center border-b-2 font-medium text-sm flex justify-center items-center`}
                                                onClick={() => setActiveTab('settings')}
                                            >
                                                <Settings size={16} className="mr-2"/>
                                                User Settings
                                            </button>
                                        </nav>
                                    </div>

                                    {/* Tab content */}
                                    <div className="p-4">
                                        {activeTab === 'courses' ? (
                                            <div>
                                                {isLoading ? (
                                                    <div className="flex justify-center py-8">
                                                        <div
                                                            className="animate-spin rounded-full h-8 w-8 border-b-2 border-red-800"></div>
                                                    </div>
                                                ) : courses.length === 0 ? (
                                                    <div className="text-center py-8">
                                                        <svg xmlns="http://www.w3.org/2000/svg"
                                                             className="h-12 w-12 mx-auto text-gray-400" fill="none"
                                                             viewBox="0 0 24 24" stroke="currentColor">
                                                            <path strokeLinecap="round" strokeLinejoin="round"
                                                                  strokeWidth={1}
                                                                  d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
                                                        </svg>
                                                        <p className="mt-2 text-gray-500">No courses added yet.</p>
                                                        <button
                                                            className="mt-4 text-sm bg-red-800 hover:bg-red-900 text-white py-2 px-4 rounded flex items-center mx-auto"
                                                            onClick={() => setShowAddCourseModal(true)}
                                                        >
                                                            <Plus size={16} className="mr-2"/>
                                                            Add Your First Course
                                                        </button>
                                                    </div>
                                                ) : (
                                                    <div className="overflow-x-auto">
                                                        <table className="min-w-full divide-y divide-gray-200">
                                                            <thead className="bg-gray-50">
                                                            <tr>
                                                                <th scope="col"
                                                                    className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                                    Course
                                                                </th>
                                                                <th scope="col"
                                                                    className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                                    CRN
                                                                </th>
                                                                <th scope="col"
                                                                    className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                                    Professor
                                                                </th>
                                                                <th scope="col" className="relative px-6 py-3">
                                                                    <span className="sr-only">Actions</span>
                                                                </th>
                                                            </tr>
                                                            </thead>
                                                            <tbody className="bg-white divide-y divide-gray-200">
                                                            {courses.map(course => (
                                                                <tr key={course.id} className="hover:bg-gray-50">
                                                                    <td className="px-6 py-4 whitespace-nowrap">
                                                                        <div
                                                                            className="font-medium text-gray-900">{course.course_name}</div>
                                                                    </td>
                                                                    <td className="px-6 py-4 whitespace-nowrap">
                                                                        <div
                                                                            className="text-gray-900">{course.crn}</div>
                                                                    </td>
                                                                    <td className="px-6 py-4 whitespace-nowrap">
                                                                        <div
                                                                            className="text-gray-900">{course.professor}</div>
                                                                    </td>
                                                                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                                                        <button
                                                                            className="text-red-600 hover:text-red-900 flex items-center justify-end"
                                                                            onClick={() => handleDeleteCourse(course.id)}
                                                                        >
                                                                            <Trash2 size={16} className="mr-1"/>
                                                                            Delete
                                                                        </button>
                                                                    </td>
                                                                </tr>
                                                            ))}
                                                            </tbody>
                                                        </table>
                                                    </div>
                                                )}
                                            </div>
                                        ) : (
                                            <div className="max-w-md mx-auto">
                                                <h3 className="text-lg font-medium mb-4">User Settings</h3>
                                                <form className="space-y-4">
                                                    <div>
                                                        <label className="block text-sm font-medium text-gray-700">User
                                                            Name</label>
                                                        <input
                                                            type="text"
                                                            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-red-500 focus:ring-red-500"
                                                            value={selectedUser.name}
                                                            readOnly
                                                        />
                                                    </div>
                                                    <div>
                                                        <label className="block text-sm font-medium text-gray-700">Webhook
                                                            URL</label>
                                                        <input
                                                            type="text"
                                                            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-red-500 focus:ring-red-500"
                                                            value={selectedUser.webhook_url}
                                                            readOnly
                                                        />
                                                    </div>
                                                    <div className="pt-2">
                                                        <button
                                                            type="button"
                                                            className="inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-red-600 text-base font-medium text-white hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
                                                            onClick={() => handleDeleteUser(selectedUser.id)}
                                                        >
                                                            Delete User
                                                        </button>
                                                    </div>
                                                </form>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <div className="bg-white shadow rounded-lg p-8 text-center">
                                <div
                                    className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-red-100">
                                    <Bell size={24} className="text-red-800"/>
                                </div>
                                <h3 className="mt-6 text-lg font-medium text-gray-900">Welcome to HowdySeek 😎</h3>
                                <p className="mt-2 text-sm text-gray-500">
                                    To get started, add a user with a Discord webhook to receive notifications when
                                    course availability changes.
                                </p>
                                <div className="mt-6">
                                    <button
                                        type="button"
                                        className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-red-800 hover:bg-red-900 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
                                        onClick={() => setShowAddUserModal(true)}
                                    >
                                        <Plus size={16} className="mr-2"/>
                                        Add Your First User
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </main>

            {/* Add User Modal */}
            <Modal
                isOpen={showAddUserModal}
                onClose={() => setShowAddUserModal(false)}
                title="Add User with Discord Webhook"
            >
                <form ref={userFormRef} onSubmit={handleAddUser} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-700">User Name</label>
                        <input
                            type="text"
                            name="name"
                            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-red-500 focus:ring-red-500"
                            placeholder="Michael Tran"
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-700">Discord Webhook URL</label>
                        <input
                            type="text"
                            name="webhook_url"
                            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-red-500 focus:ring-red-500"
                            placeholder="https://discord.com/api/webhooks/..."
                        />
                    </div>
                    <div className="pt-2">
                        <button
                            type="submit"
                            className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-red-800 text-base font-medium text-white hover:bg-red-900 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
                        >
                            Add User
                        </button>
                    </div>
                </form>
            </Modal>

            {/* Add Course Modal */}
            <Modal
                isOpen={showAddCourseModal}
                onClose={() => setShowAddCourseModal(false)}
                title="Add Course to Monitor"
            >
                <form ref={courseFormRef} onSubmit={handleAddCourse} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-700">Course Name</label>
                        <input
                            type="text"
                            name="course_name"
                            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-red-500 focus:ring-red-500"
                            placeholder="MATH 251"
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-700">CRN</label>
                        <input
                            type="text"
                            name="crn"
                            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-red-500 focus:ring-red-500"
                            placeholder="123456"
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-700">Professor</label>
                        <input
                            type="text"
                            name="professor"
                            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-red-500 focus:ring-red-500"
                            placeholder="Lee, Sang Rae"
                        />
                    </div>
                    <div className="pt-2">
                        <button
                            type="submit"
                            className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-red-800 text-base font-medium text-white hover:bg-red-900 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
                        >
                            Add Course
                        </button>
                    </div>
                </form>
            </Modal>

            {/* Settings Modal */}
            <Modal
                isOpen={showSettingsModal}
                onClose={() => setShowSettingsModal(false)}
                title="Application Settings"
            >
                <form ref={settingsFormRef} onSubmit={handleUpdateSettings} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-700">Minimum Refresh Interval
                            (seconds)</label>
                        <input
                            type="number"
                            name="min_interval"
                            min="0"
                            step="1"
                            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-red-500 focus:ring-red-500"
                            defaultValue={refreshSettings.min_refresh_interval}
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-700">Maximum Refresh Interval
                            (seconds)</label>
                        <input
                            type="number"
                            name="max_interval"
                            min="0"
                            step="1"
                            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-red-500 focus:ring-red-500"
                            defaultValue={refreshSettings.max_refresh_interval}
                        />
                    </div>
                    <div className="pt-2">
                        <button
                            type="submit"
                            className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-red-800 text-base font-medium text-white hover:bg-red-900 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
                        >
                            Update Settings
                        </button>
                    </div>
                </form>
            </Modal>
        </div>
    );
};

export default App;